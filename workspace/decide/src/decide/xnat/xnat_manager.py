"""XNAT Wrapper."""

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional, Tuple, Union

import xnat
from tqdm import tqdm


class XNATManager:
    """Manages connection and operations with an XNAT server."""

    def __init__(
        self,
        host: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        project: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        *,
        load_patients: bool = False,
    ):
        """Wrapper for XNAT Session.

        :param Optional[str] host: host url, will be taken from env if not given, defaults to None
        :param Optional[str] username: username, will be taken from env if not given, defaults to None
        :param Optional[str] password: password, will be taken from env if not given, defaults to None
        :param Optional[str] project: project, will be taken from env if not given, defaults to None
        :param Optional[logging.Logger] logger: Optional logger object, defaults to None
        :param bool load_patients: If true, makes a subject label dict., defaults to False
        :raises ValueError: If XNAT xredentials not given or found.
        """
        self._host = (host or os.getenv("XNAT_URL", "")).rstrip("/")
        self._username = username or os.getenv("XNAT_USER", "")
        self._password = password or os.getenv("XNAT_PASSWORD", "")
        self.project = project or os.getenv("XNAT_PROJECT", "")
        self.session = None
        self.session_connected = False
        self.subject_label_lookup = {}
        self.subject_label_list = []
        self.logger = logger or self._create_default_logger()

        if not all([self._host, self._username, self._password, self.project]):
            raise ValueError(
                "Missing required XNAT credentials or project. Please provide them or set environment variables."
            )

        if load_patients:
            self.get_patient_lookup_dict()

    def _create_default_logger(self) -> logging.Logger:
        """Makes default logger.

        :return logging.Logger: Logger
        """
        logger = logging.getLogger("XNATManager")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def __enter__(self):
        """Enter context."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit context."""
        if exc_type:
            self.logger.error(f"Exception: {exc_type.__name__} - {exc_value}")
        self.disconnect()
        return exc_type is None

    def connect(self):
        """Establishes a session with the XNAT server."""
        if not self.session_connected:
            try:
                self.session = xnat.connect(self._host, user=self._username, password=self._password)
                self.session_connected = True
                self.logger.info("Connected to XNAT.")
            except Exception as e:
                self.logger.error(f"Failed to connect to XNAT: {e}")
                raise

    def disconnect(self):
        """Terminates the session with the XNAT server."""
        if self.session and self.session_connected:
            self.session.disconnect()
            self.session_connected = False
            self.logger.info("Disconnected from XNAT.")

    @contextmanager
    def get_connection(self):
        """Context manager for XNAT connection."""
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()

    def get_patient_lookup_dict(self):
        """Makes the subject label lookup dict."""
        with self.get_connection():
            subject_label_lookup = {
                value.label: key for key, value in self.session.projects[self.project].subjects.items()
            }
            self.subject_label_lookup = dict(sorted(subject_label_lookup.items(), key=lambda item: item[0]))
            self.subject_label_list = list(self.subject_label_lookup.keys())
            self.logger.info(f"Loaded {len(self.subject_label_list)} subjects.")

    def get_subject(self, subject_label: str):
        """Get the subject xnat object, given the label."""
        return self.session.subjects[self.subject_label_lookup[subject_label]]

    def get_experiment(self, subject_label: str):
        """Retrieves the first experiment for a subject."""
        subject = self.get_subject(subject_label)
        experiment_id = next(iter(subject.experiments))
        return self.session.experiments[experiment_id]

    def get_patient_experiment(
        self, resume_from: Optional[str] = None
    ) -> Generator[Tuple[str, "xnat.Experiment"], None, None]:
        """Yields subject label and experiment for each patient."""
        subject_list = self.subject_label_list
        if resume_from:
            try:
                start_index = subject_list.index(resume_from)
                subject_list = subject_list[start_index:]
            except ValueError:
                self.logger.warning(f"Subject label '{resume_from}' not found.")
                return

        with tqdm(subject_list, colour="red") as pbar:
            for label in pbar:
                pbar.set_description(f"Processing Subject: {label}")
                try:
                    experiment = self.get_experiment(label)
                    yield label, experiment
                except KeyError:
                    self.logger.warning(f"Experiment for subject '{label}' not accessible.")

    def get_or_create_resource(self, experiment, resource_label):
        """Get or create a resource in the given experiment.

        :param (xnat experiment object) experiment: the target experiment.
        :param str resource_label: label for the resource.
        :return (xnat resource object): xnat resource in the given experiment.
        """
        if resource_label in experiment.resources:
            xnat_resource = experiment.resources[resource_label]
            return xnat_resource
        else:
            xnat_resource = self.session.classes.ResourceCatalog(parent=experiment, label=resource_label)
            return xnat_resource

    def upload_to_resource(self, experiment, resource_label: str, file_path: Union[str, Path]):
        """Upload a file to the specified resource. If the file already exists, it will be replaced.

        :param _type_ experiment: The experiment object or identifier.
        :param str resource_label: Label of the resource to upload the file to.
        :param Union[str, Path] file_path: Path to the file to be uploaded.
        :raises FileNotFoundError: If the file path does not exist.
        :raises RuntimeError: If the upload fails.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"The file path '{file_path}' does not exist.")

        try:
            resource = self.get_or_create_resource(experiment, resource_label)

            # Delete the file if it already exists in the resource
            if file_path.name in resource.files:
                resource.files[file_path.name].delete()
                self.logger.debug(f"Deleted existing file '{file_path.name}' from resource '{resource_label}'.")

            # Upload the file
            resource.upload(file_path, file_path.name)
            self.logger.debug(f"Uploaded '{file_path.name}' to resource '{resource_label}'.")

        except Exception as e:
            self.logger.error(f"Failed to upload '{file_path.name}' to resource '{resource_label}': {e}")
            raise RuntimeError(f"Failed to upload resource: {e}")

    def upload_directory(
        self, experiment, resource_label: str, source_dir: Union[str, Path], file_type: Optional[str] = None
    ):
        """Upload files from a directory to a specified resource.

        :param _type_ experiment: The experiment object or identifier to which files are uploaded.
        :param str resource_label: Label of the resource to upload files to.
        :param Union[str, Path] source_dir: Path to the source directory containing files.
        :param Optional[str] file_type: File extension filter (e.g., '.nii.gz').
        If provided, only files matching the extension will be uploaded. Defaults to None., defaults to None
        :raises FileNotFoundError: If the source directory does not exist or is not a directory.
        """
        source_path = Path(source_dir)

        if not source_path.exists() or not source_path.is_dir():
            raise FileNotFoundError(f"The source directory '{source_path}' does not exist or is not a directory.")

        if file_type:
            files = source_path.rglob(f"*{file_type}")
            message = f"All '{file_type}' files uploaded from {source_path.name} to {resource_label}."
        else:
            files = source_path.rglob("*")
            message = f"All files uploaded from {source_path.name} to {resource_label}."

        for file in files:
            if file.is_file():
                self.upload_to_resource(experiment, resource_label, file)

        self.logger.info(message)

    def delete_resource(self, experiment, resource_label: str):
        """Delete a resource from an experiment, if it exists.

        :param (xnat experiment object) experiment: target experiment.
        :param str resource_label: the resource label.
        """
        if resource_label in experiment.resources:
            experiment.resources[resource_label].delete()
            self.logger.info(f"Deleted Resource {resource_label}.")

    def download_files(self, dest_dir: Union[str, Path], files: List, desc: Optional[str] = None):
        """Download files from XNAT.

        :param Union[str, Path] dest_dir: destination directory.
        :param List files:list of xnat file objects.
        :param Optional[str] desc: Description for progress bar, defaults to None
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        with tqdm(files, colour="red", desc=f"Downloading {desc or 'Files'}", leave=False) as pbar:
            for file in pbar:
                try:
                    file.download(dest_dir / file.name, verbose=False)
                    self.logger.debug(f"Downloaded {file.name} to {dest_dir}.")
                except Exception as e:
                    self.logger.warning(f"Failed to download {file.name}: {e}")

    def download_resources(self, dest_dir: Union[str, Path], resource):
        """Download xnat resource.

        :param Union[str, Path] dest_dir: destination directory.
        :param (xnat resource object) resource: the target xant resource object.
        """
        self.download_files(dest_dir, list(resource.files.values()))

    def download_scan(self, dest_dir: Union[str, Path], scan):
        """Downlaod xnat scan.

        :param Union[str, Path] dest_dir: destination directory.
        :param (xnat scan object) scan: the target xnat scan object.
        """
        self.download_files(dest_dir, list(scan.files.values()), desc=scan.modality)

    def download_modality(self, experiment, dest_dir: Union[str, Path], modality: Union[str, list]):
        """Downlaod scans of specified modality.

        :param (xnat experiment object) experiment: the target experiment.
        :param Union[str, Path] dest_dir: destination directory.
        :param Union[str, list] modality: the needed modality/modalities.
        """
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        if isinstance(modality, str):
            modality = [modality]

        for scan in experiment.scans.values():
            try:
                files = list(scan.files.values())
                if not files:
                    self.logger.warning(f"No files found in scan {scan.id}. Skipping.")
                    continue

                first_file = files[0]
                file_modality = scan.modality or getattr(first_file, "modality", None)

                if file_modality in modality:
                    self.logger.info(f"Downloading scan {scan.id} with modality '{file_modality}'.")
                    self.download_scan(dest_dir / file_modality, scan)
                else:
                    self.logger.info(f"Skipping scan {scan.id} with modality '{file_modality}'.")
            except Exception as e:
                self.logger.warning(f"Failed to process scan {scan.id}: {e}")
