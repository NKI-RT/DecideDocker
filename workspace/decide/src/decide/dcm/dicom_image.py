"""Image Conversion."""

import logging
import subprocess
from pathlib import Path
from typing import List, Union

import SimpleITK as sitk

from decide.utils.logger import setup_logger


class ImageConvertor:
    """Contains static methods to convert DICOM image to NIfTI."""

    @staticmethod
    def dcm_img_to_nifti_platimatch(dicom_dir: str, output_file: str, logger: logging.Logger = None) -> bool:
        """Convert a DICOM image directory to a NIfTI file using Plastimatch.

        :param str dicom_dir: Path to the input DICOM directory.
        :param str output_file: Path to the output .nii.gz file.
        :param logging.Logger logger: Optional logger object, defaults to None
        :return bool: True if conversion is successful, False otherwise.
        """
        logger = logger or setup_logger(level=logging.INFO)
        logger.info("\n")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = ["plastimatch", "convert", "--input", str(dicom_dir), "--output-img", str(output_file)]

        try:
            logger.info(f"Starting image conversion: {command}")
            result = subprocess.run(command, capture_output=True, text=True)

            logger.info(f"stdout: {result.stdout}")
            logger.info(f"stderr: {result.stderr}")

            if result.returncode != 0:
                logger.error(f"Image conversion failed with return code {result.returncode}")
                logger.info("\n\n")
                return False
            logger.info(f"Image conversion successful. Output saved to: {output_file}")
            logger.info("\n\n")
            return True

        except Exception as e:
            logger.error(f"Exception during image conversion: {str(e)}")
            logger.info("\n\n")
            return False

    @staticmethod
    def dcm_rtstruct_to_nifti_platimatch(
        rtstruct_file: str, referenced_ct: str, output_prefix: str, logger: logging.Logger = None
    ) -> bool:
        """Convert a DICOM RTSTRUCT file to NIfTI ROI masks using Plastimatch.

        :param str rtstruct_file: Path to the RTSTRUCT DICOM file or directory.
        :param str referenced_ct: Path to the referenced CT DICOM directory.
        :param str output_prefix: Prefix for the output NIfTI mask files.
        :param logging.Logger logger: Optional logger object, defaults to None
        :return bool: True if conversion is successful, False otherwise.
        """
        logger = logger or setup_logger(level=logging.INFO)
        logger.info("\n")

        output_path = Path(output_prefix).parent
        output_path.mkdir(parents=True, exist_ok=True)

        command = [
            "plastimatch",
            "convert",
            "--input",
            str(rtstruct_file),
            "--referenced-ct",
            str(referenced_ct),
            "--output-prefix",
            str(output_prefix),
            "--prefix-format",
            "nii.gz",
            "--prune-empty",
        ]

        try:
            logger.info(f"Starting RTSTRUCT conversion: {command}")
            result = subprocess.run(command, capture_output=True, text=True)

            logger.info(f"stdout: {result.stdout}")
            logger.info(f"stderr: {result.stderr}")

            if result.returncode != 0:
                logger.error(f"RTSTRUCT conversion failed with return code {result.returncode}")
                logger.info("\n\n")
                return False

            logger.info(f"RTSTRUCT conversion successful. Output saved with prefix: {output_prefix}")
            logger.info("\n\n")
            return True

        except Exception as e:
            logger.error(f"Exception during RTSTRUCT conversion: {str(e)}")
            logger.info("\n\n")
            return False

    @staticmethod
    def dcm_img_to_nifti_sitk(
        input_files: Union[str, Path, List[Union[str, Path]]],
        output_name: Union[str, Path],
        logger: logging.Logger = None,
    ) -> bool:
        """Converts a DICOM CT image series (directory or list of files) to a NIFTI image using sitk.

        :param Union[str, Path, List[Union[str, Path]]] input_files: Path to the DICOM directory or a list of DICOM file
        paths.
        :param Union[str, Path] output_name: Path to the output NIFTI file (must end with .nii.gz).
        :param logging.Logger logger: Optional logger object, defaults to None
        :return bool: True if the conversion was successful, False otherwise.
        """
        logger = logger or setup_logger(level=logging.INFO)

        if not input_files:
            logger.error("Input path or file list is empty.")
            return False

        reader = sitk.ImageSeriesReader()

        try:
            if isinstance(input_files, (str, Path)):
                input_path = Path(input_files)
                dicom_files = reader.GetGDCMSeriesFileNames(str(input_path))
            elif isinstance(input_files, list):
                dicom_files = ImageConvertor.arrange_files(input_files, logger)
                if not dicom_files:
                    logger.error("Failed to arrange DICOM files.")
                    return False
            else:
                logger.error("Invalid input type. Must be a path or list of paths.")
                return False

            logger.debug(f"Found {len(dicom_files)} DICOM files.")
            reader.SetFileNames(dicom_files)
            image = reader.Execute()
        except Exception as e:
            logger.error(f"Error reading DICOM series: {e}")
            return False

        output_path = Path(output_name)
        if not output_path.name.endswith(".nii.gz"):
            logger.error("Output file must end with .nii.gz")
            return False

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sitk.WriteImage(image, str(output_path))
            logger.info(f"Saved NIFTI image to: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving NIFTI image: {e}")
            return False

    @staticmethod
    def arrange_files(list_of_files: List[Union[str, Path]], logger: logging.Logger = None) -> Union[List[str], None]:
        """Sorts a list of DICOM files based on their slice location (z-position).

        :param List[Union[str, Path]] list_of_files: A list of DICOM file paths.
        :param logging.Logger logger: Optional logger object, defaults to None
        :return Union[List[str], None]: A sorted list of DICOM file paths, or None if sorting fails.
        """
        logger = logger or setup_logger(level=logging.INFO)

        z_positions = []
        valid_files = []

        for file in list_of_files:
            file_path = Path(file)
            try:
                dicom_image = sitk.ReadImage(str(file_path))
                z = float(dicom_image.GetMetaData("0020|0013"))  # Instance Number
                z_positions.append(z)
                valid_files.append(str(file_path))
            except Exception as e:
                logger.warning(f"Skipping file {file_path}: {e}")

        if not z_positions:
            logger.error("No valid DICOM files with z-position metadata found.")
            return None

        sorted_indices = sorted(range(len(z_positions)), key=lambda i: z_positions[i])
        sorted_files = [valid_files[i] for i in sorted_indices]

        logger.debug(f"Sorted {len(sorted_files)} DICOM files by z-position.")
        return sorted_files
