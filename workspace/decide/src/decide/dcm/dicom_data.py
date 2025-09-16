"""."""

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

import pydicom
import yaml
from tqdm import tqdm

from decide.dcm.dicom_metadata import DICOMNestedTags
from decide.paths import CONFIG_DIR
from decide.utils.logger import setup_logger


class DICOMData:
    """Manages and organizes DICOM data from directories or JSON files."""

    def __init__(
        self,
        input_source: Union[Path, str, List],
        configuration: Optional[Union[Path, str]] = CONFIG_DIR / "dicomdata_config.yaml",
        logger=None,
    ):
        """Initializes the DICOMData object with input source and optional configuration.

        :param Union[Path, str, List] input_source: The directory with dicom files or list of files or json file made
        with this class.
        :param Optional[Union[Path, str]] configuration: Configuration for metadata,
        defaults to CONFIG_DIR/"dicomdata_config.yaml"
        :param _type_ logger: The Optional Logger Object, defaults to None
        :raises ValueError: For invalida JSON or YAML files.
        """
        self.source_file = ""
        self.logger = logger if logger else setup_logger(name="DICOM DataBase")
        self.data = {}

        if configuration:
            self.load_configuration(configuration)
        else:
            self.config = {}

        if isinstance(input_source, list):
            self.source_dir = input_source
            self.logger.info(f"Using source: a List of length {len(input_source)}!")
        else:
            self.logger.info(f"Using source: {input_source}")
            input_source = Path(input_source)
            if not input_source.exists():
                self.logger.error(f"Invalid input Directory/ .json File: {input_source}")
                raise ValueError(f"Invalid input Directory/ .json File: {input_source}")
            if input_source.is_dir():
                self.logger.info(f"DB Object initializing from Directory : {input_source}")
                self.source_dir = input_source
                self.load_from_directory()
            elif input_source.is_file() and input_source.suffix.lower() == ".json":
                self.logger.info(f"DB Object initializing from File : {input_source}")
                self.source_file = input_source
                self.load_from_file()
                self.source_dir = self.data.get("DirectoryPath", "")
            else:
                self.logger.error(f"Invalid input .json file: {input_source}")
                raise ValueError(f"Invalid input .json file: {input_source}")

    def load_configuration(self, configuration):
        """Loads configuration from a YAML file."""
        configuration = Path(configuration)
        if configuration.exists() and configuration.is_file() and configuration.suffix in (".yml", ".yaml"):
            self.logger.info(f"DB Object initializing from File : {configuration}")
            self.load_configuration_from_yaml(configuration)
        else:
            self.logger.error(f"Invalid input .yaml file: {configuration}")
            raise ValueError(f"Invalid input .yaml file: {configuration}")

    def load_configuration_from_yaml(self, configuration):
        """Parses YAML configuration with custom callable resolution."""

        def get_static_method_from_class(class_obj, method_name):
            if hasattr(class_obj, method_name):
                attr = getattr(class_obj, method_name)
                if callable(attr):
                    return attr
            return None

        class CustomLoader(yaml.SafeLoader):
            pass

        def resolve_callable(loader, node):
            name = loader.construct_scalar(node)
            return get_static_method_from_class(DICOMNestedTags, name)

        CustomLoader.add_constructor("!callable", resolve_callable)

        with open(configuration, "r") as file:
            self.config = yaml.load(file, Loader=CustomLoader)

    def load_from_file(self):
        """Loads DICOM metadata from a JSON file."""
        with open(self.source_file, "r", encoding="utf-8") as json_file:
            self.data = json.load(json_file)

    def load_from_directory(self):
        """Organizes DICOM files from a directory using configuration if available."""
        if self.config:
            self.organize_dicom_with_configuration()
        else:
            self.data = self.organize_dicom_files(self.source_dir)

    def organize_dicom_with_configuration(self):
        """Organizes DICOM files using configuration parameters."""
        modalities = self.config.get("modalities", [])
        additional_tags = self.config.get("additional_tags", {})
        modality_specific = self.config.get("modality_specific", {})
        self.data = self.organize_dicom_files(
            input_dir=self.source_dir,
            modalities=modalities,
            additional_tags=additional_tags,
            modality_specific=modality_specific,
        )

    def save_db(self, output_json):
        """Saves organized DICOM metadata to a JSON file."""
        if output_json:
            with open(output_json, "w", encoding="utf-8") as json_file:
                json.dump(self.data, json_file, indent=4)
            if not self.source_file:
                self.source_file = output_json

    def organize_dicom_files(
        self,
        input_dir: Union[str, Path, List[str]],
        modalities: Optional[List[str]] = None,
        additional_tags: Optional[Dict[str, List[str]]] = None,
        modality_specific: Optional[
            Dict[str, Dict[str, List[Union[str, Callable[[pydicom.FileDataset], Tuple[str, str]]]]]]
        ] = None,
    ) -> Dict:
        """Organizes DICOM files into a hierarchical structure based on metadata.

        :param Union[str, Path, List[str]] input_dir: DICOM Directory
        :param Optional[List[str]] modalities: Modalities of interest, if given exclues the others, defaults to None
        :param Optional[Dict[str, List[str]]] additional_tags: Aadditional metadata tags, defaults to None
        :param Optional[ Dict[str, Dict[str, List[Union[str, Callable[[pydicom.FileDataset], Tuple[str, str]]]]]] ]
        modality_specific: Modality specific metadata, defaults to None
        :raises ValueError: If no DICOM files found.
        :return Dict: Collected and Organized Metadata.
        """
        dicom_files = self.collect_files(input_dir)
        if not dicom_files:
            raise ValueError(f"No files found in the directory: {input_dir}")
        organized_data = self.collect_metadata(dicom_files, modalities, additional_tags, modality_specific)
        organized_data["DirectoryPath"] = (
            str(input_dir) if isinstance(input_dir, (Path, str)) else [str(i) for i in input_dir]
        )
        return organized_data

    def collect_files(self, input_dir: Union[Path, str, List[str]]) -> List[Path]:
        """Collects all file paths from the input directory or list of directories.

        :param Union[Path, str, List[str]] input_dir: DICOM Directory
        :raises ValueError: If directory does not exist.
        :return List[Path]: List of all files.
        """
        if isinstance(input_dir, list):
            dicom_files = []
            for dir_ in tqdm(input_dir, desc="Collecting Files"):
                dicom_files += [file_path for file_path in Path(dir_).rglob("*") if file_path.is_file()]
        else:
            input_dir = Path(input_dir)
            if not input_dir.exists() or not input_dir.is_dir():
                raise ValueError(f"Invalid input directory: {input_dir}")
            if not input_dir.is_absolute():
                input_dir = input_dir.resolve()
            dicom_files = [file for file in input_dir.rglob("*") if file.is_file()]
        return dicom_files

    def collect_metadata(
        self,
        dicom_files: List[Path],
        modalities: Optional[List[str]] = None,
        additional_tags: Optional[Dict[str, List[str]]] = None,
        modality_specific: Optional[
            Dict[str, Dict[str, List[Union[str, Callable[[pydicom.FileDataset], Tuple[str, str]]]]]]
        ] = None,
    ) -> Dict:
        """Processes DICOM files and organizes metadata hierarchically.

        :param List[Path] dicom_files: List of files.
        :param Optional[List[str]] modalities: Modalities to consider, defaults to None
        :param Optional[Dict[str, List[str]]] additional_tags: Additional metadata tags needed, defaults to None
        :param Optional[ Dict[str, Dict[str, List[Union[str, Callable[[pydicom.FileDataset], Tuple[str, str]]]]]] ]
        modality_specific: MOdality specific metadata tags, defaults to None
        :raises ValueError: If nothing to output.
        :return Dict: Organized DICOM Metadata
        """
        organized_data = {"Patients": {}}
        for f in tqdm(dicom_files, desc="Processing DICOM files"):
            result = self.process_dicom_file(f, modalities, additional_tags, modality_specific)
            if not result:
                continue
            patient_data = organized_data["Patients"].setdefault(result["PatientID"], {})
            patient_data.update(result["Patients"])
            studies = patient_data.setdefault("Studies", {})
            study_data = studies.setdefault(result["StudyInstanceUID"], {})
            study_data.update(result["Studies"])
            series = study_data.setdefault("Series", {})
            series_data = series.setdefault(result["SeriesInstanceUID"], {})
            series_data.update(result["Series"])
            instances = series_data.setdefault("Instances", {})
            instance_data = instances.setdefault(result["SOPInstanceUID"], {})
            instance_data.update(result["Instances"])
        if not organized_data:
            raise ValueError("No valid DICOM files found!")
        return organized_data

    def process_dicom_file(
        self,
        file_path: Union[str, Path],
        modalities: Optional[List[str]] = None,
        additional_tags: Optional[Dict[str, List[str]]] = None,
        modality_specific: Optional[
            Dict[str, Dict[str, List[Union[str, Callable[[pydicom.FileDataset], Tuple[str, str]]]]]]
        ] = None,
    ) -> Optional[Dict]:
        """Processes a single DICOM file and extracts relevant metadata.

        :param Union[str, Path] file_path: File
        :param Optional[List[str]] modalities: Modalities to consider, defaults to None
        :param Optional[Dict[str, List[str]]] additional_tags: Additional metadata tags, defaults to None
        :param Optional[ Dict[str, Dict[str, List[Union[str, Callable[[pydicom.FileDataset], Tuple[str, str]]]]]] ]
        modality_specific: Modality specific metadata tags, defaults to None
        :return Optional[Dict]: Interested metadata of a DICOM File.
        """
        try:
            dicom = pydicom.dcmread(file_path, stop_before_pixels=True)
            patient_id = str(getattr(dicom, "PatientID", "Unknown"))
            study_uid = str(getattr(dicom, "StudyInstanceUID", "Unknown"))
            series_uid = str(getattr(dicom, "SeriesInstanceUID", "Unknown"))
            instance_uid = str(getattr(dicom, "SOPInstanceUID", "Unknown"))
            modality = str(getattr(dicom, "Modality", "Unknown"))
            if modalities and modality not in modalities:
                return None
            file_data = {
                "PatientID": patient_id,
                "StudyInstanceUID": study_uid,
                "SeriesInstanceUID": series_uid,
                "SOPInstanceUID": instance_uid,
                "Series": {"Modality": modality},
                "Instances": {"FilePath": str(file_path)},
                "Patients": {},
                "Studies": {},
            }
            if additional_tags:
                for tag_level, tag_list in additional_tags.items():
                    for tag in tag_list:
                        file_data[tag_level][tag] = str(getattr(dicom, tag, "Unknown"))
            if modality_specific and modality in modality_specific:
                for tag_level, tag_list in modality_specific[modality].items():
                    for tag in tag_list:
                        try:
                            if callable(tag):
                                tag_name, tag_value = tag(dicom)
                                file_data[tag_level][tag_name] = str(tag_value)
                            elif isinstance(tag, str):
                                file_data[tag_level][tag] = str(getattr(dicom, tag, "Unknown"))
                        except Exception:
                            continue
            return file_data
        except Exception:
            return None

    def list_patients(self):
        """Return a list of patient IDs."""
        return list(self.data.get("Patients", {}).keys())

    def get_patient(self, patientid):
        """Return a Patient instance for the given patient ID."""
        patient_data = self.data.get("Patients", {}).get(patientid)
        if patient_data:
            return Patient(patient_data, patientid)
        return None


class Patient:
    """Represents a DICOM patient."""

    def __init__(self, data: dict, patientid: str):
        """DICOM Patient."""
        self.data = data
        self.patientid = patientid

    def get_modality(self, modality: str) -> List:
        """Get a specified modality.

        :param str modality: DICOMModality
        :return List: List of the specified modality objects with their metadata
        """
        results = []
        for studyuid, study_data in self.data.get("Studies", {}).items():
            study = Study(study_data, studyuid, self)
            for seriesuid, series_data in study_data.get("Series", {}).items():
                if series_data.get("Modality") == modality:
                    if modality == "CT":
                        results.append(CT(series_data, seriesuid, study))
                    elif modality == "RTSTRUCT":
                        results.append(RTSTRUCT(series_data, seriesuid, study))
                    else:
                        results.append(Series(series_data, seriesuid, study))
        return results


class Study:
    """Represents a DICOM study."""

    def __init__(self, data: dict, studyuid: str, patient: Patient):
        """DICOM Study.

        :param dict data: DICOM Metadata
        :param str studyuid: DICOM StudyInstanceUID
        :param Patient patient: The patient object
        """
        self.data = data
        self.studyuid = studyuid
        self.patient = patient


class Series:
    """Base class for a DICOM series."""

    def __init__(self, data: dict, seriesinstanceuid: str, study: Study):
        """DICOM Series.

        :param dict data: DICOM Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Study study: The study object
        """
        self.data = data
        self.seriesinstanceuid = seriesinstanceuid
        self.study = study
        self.patient = study.patient

    def get_files(self):
        """Return the Files in this series."""
        files = []
        for _, instance_data in self.data.get("Instances", {}).items():
            files.append(instance_data.get("FilePath", {}))
        return files


class CT(Series):
    """CT modality series."""

    def __init__(self, data: dict, seriesinstanceuid: str, study: Study):
        """DICOM CT.

        :param dict data: DICOM Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Study study: The study object
        """
        super().__init__(data, seriesinstanceuid, study)


class RTSTRUCT(Series):
    """RTSTRUCT modality series with CT reference finder."""

    def __init__(self, data: dict, seriesinstanceuid: str, study: Study):
        """DICOM RTSTRUCT.

        :param dict data: DICOM Metadata
        :param str seriesinstanceuid: DICOM SeriesInstanceUID
        :param Study study: The study object
        """
        super().__init__(data, seriesinstanceuid, study)

    def get_ct(self):
        """Find the CT series referenced by this RTSTRUCT."""
        ref_uid = self.data.get("ReferencedSeriesUID")
        for studyuid, study_data in self.patient.data.get("Studies", {}).items():
            for uid, series in study_data.get("Series", {}).items():
                if uid == ref_uid and series.get("Modality") == "CT":
                    return CT(series, uid, Study(study_data, studyuid, self.patient))
        return None
