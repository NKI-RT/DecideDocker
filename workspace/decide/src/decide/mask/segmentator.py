"""Module for Autosegmentation of Thoracic Structures."""

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Union

import SimpleITK as sitk
import yaml
from platipy.imaging.projects.cardiac.run import run_hybrid_segmentation
from totalsegmentator.python_api import totalsegmentator

from decide.paths import CONFIG_DIR
from decide.utils.logger import setup_logger


class ImageSegmentator(ABC):
    """Abstract base class for image segmentation models."""

    @abstractmethod
    def run_segmentator(self, nifti_image: Union[str, Path], output_dir: Union[str, Path]) -> None:
        """Run the segmentation model on the given image.

        :param Union[str, Path] nifti_image: Path to the input NIfTI image.
        :param Union[str, Path] output_dir: Directory to save the segmentation output.
        """
        pass


class TSModel(ImageSegmentator):
    """TotalSegmentator model wrapper."""

    def __init__(
        self,
        ts_configuration: Union[List[str], str, Path] = CONFIG_DIR / "config_total_segmentator.yaml",
        logger: logging.Logger = None,
    ):
        """Initialize the TSModel with optional ROI subset configuration.

        :param Union[List[str], str, Path] ts_configuration: List of ROI names or path to YAML config file.
        defaults to CONFIG_DIR/"config_total_segmentator.yaml"
        :param logging.Logger logger: Optional logger object, defaults to a new logger with INFO level.
        """
        self.logger = logger or setup_logger(level=logging.INFO)

        self.roi_subset = None
        if ts_configuration:
            if isinstance(ts_configuration, list):
                self.roi_subset = ts_configuration
            else:
                config_path = Path(ts_configuration)
                if config_path.is_file():
                    with open(config_path, "r") as file:
                        config = yaml.safe_load(file)
                        self.roi_subset = config.get("roi_subset")

    @staticmethod
    def set_totalsegmentator_license(license_number: str) -> None:
        """Set the license for TotalSegmentator.

        :param str license_number: License key.
        """
        command = f"totalseg_set_license -l {license_number}"
        subprocess.run(command, shell=True)

    def run_segmentator(self, nifti_image: Union[str, Path], output_dir: Union[str, Path]) -> None:
        """Run TotalSegmentator on the given image with multiple tasks.

        :param Union[str, Path] nifti_image:  Path to the input NIfTI image.
        :param Union[str, Path] output_dir: Directory to save the segmentation output.
        """
        nifti_image = str(nifti_image)
        output_dir = str(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        # Run high-resolution heart segmentation
        self.logger.info("Running Heartchambers Highres Segmentation")
        totalsegmentator(nifti_image, output_dir, quiet=True, task="heartchambers_highres")

        # Rename heart segmentation outputs and delete heart_aorta.nii.gz
        self.logger.info("Renaming heartchambers_highres outputs with prefix heart_ & removing aorta")
        for file in os.listdir(output_dir):
            file_path = os.path.join(output_dir, file)
            if file == "aorta.nii.gz":
                os.remove(file_path)
            elif not file.startswith("heart_"):
                new_path = os.path.join(output_dir, f"heart_{file}")
                os.rename(file_path, new_path)

        # Run whole-body segmentation
        self.logger.info("Running Body Segmentation")
        totalsegmentator(nifti_image, output_dir, quiet=True, task="body")

        # Run default segmentation with optional ROI subset
        self.logger.info("Running 'total' Segmentation")
        totalsegmentator(nifti_image, output_dir, quiet=True, roi_subset=self.roi_subset)


class PlatityModel(ImageSegmentator):
    """Wrapper for Platipy's hybrid cardiac segmentation model."""

    def __init__(self, logger: logging.Logger = None):
        """The PlatiPy model.

        :param logging.Logger logger: Optional logger object, defaults to a new logger with INFO level.
        """
        super().__init__()
        self.logger = logger or setup_logger(level=logging.INFO)

    def run_segmentator(self, nifti_image: Union[str, Path], output_dir: Union[str, Path]) -> None:
        """Run Platipy's hybrid cardiac segmentation on the input image.

        :param Union[str, Path] nifti_image: Path to the input NIfTI image.
        :param Union[str, Path] output_dir: Directory to save the segmentation output.
        :raises RuntimeError: If segmentation or saving fails.
        """
        try:
            input_image = sitk.ReadImage(str(nifti_image))
            self.logger.info("Running hybrid Segmentation")
            auto_structures, _ = run_hybrid_segmentation(input_image)

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            self.logger.info("Saving Platipy Masks")
            for struct_name, struct_image in auto_structures.items():
                output_file = output_path / f"{struct_name}.nii.gz"
                sitk.WriteImage(struct_image, str(output_file))
        except Exception as e:
            raise RuntimeError(f"Platipy segmentation failed: {e}")
