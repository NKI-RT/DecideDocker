"""Validate the DICOM Image Series."""

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Union

import numpy as np
import pydicom


class ImageValidator:
    """DICOM Image Series Validator."""

    def __init__(self, logger: logging.Logger = None):
        """DICOM Image Series Validator.

        :param logging.Logger logger: Optional logger object, defaults to None
        """
        self.logger = logger or self._create_default_logger()

    def _create_default_logger(self) -> logging.Logger:
        logger = logging.getLogger("ImageValidator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def validate_image(self, ct_files: Union[List[Union[str, Path]], Path]) -> bool:
        """Validate the DICOM CT Image Series.

        :param Union[List[Union[str, Path]], Path] ct_files: CT Files
        :return bool: Validation Status
        """
        if isinstance(ct_files, (str, Path)):
            ct_files = sorted(Path(ct_files).glob("*.dcm"))

        if not ct_files:
            self.logger.warning("No DICOM files found.")
            return False

        metadata_list = []
        for file in ct_files:
            try:
                dicom = pydicom.dcmread(file, force=True)
                metadata_list.append(
                    {
                        "SeriesInstanceUID": getattr(dicom, "SeriesInstanceUID", None),
                        "InstanceNumber": getattr(dicom, "InstanceNumber", None),
                        "ZPosition": getattr(dicom, "ImagePositionPatient", [None, None, None])[2],
                        "Modality": getattr(dicom, "Modality", None),
                        "PixelSpacing": str(getattr(dicom, "PixelSpacing", None)),
                        "SliceThickness": str(getattr(dicom, "SliceThickness", None)),
                        "ImageOrientationPatient": str(getattr(dicom, "ImageOrientationPatient", None)),
                        "PatientID": getattr(dicom, "PatientID", None),
                        "StudyInstanceUID": getattr(dicom, "StudyInstanceUID", None),
                        "HasPixelData": hasattr(dicom, "PixelData"),
                        "FilePath": file,
                    }
                )
            except Exception as e:
                self.logger.warning(f"Failed to read {file}: {e}")

        if len(metadata_list) < 2:
            self.logger.warning("Insufficient valid DICOM slices.")
            return False

        checks = {
            "Single Series": self._check_single_series(metadata_list),
            "Equal Z-Spacing": self._check_equal_z_spacing(metadata_list),
            "Missing Slices": self._check_missing_slices(metadata_list),
            "Metadata Consistency": self._check_metadata_consistency(metadata_list),
            "Pixel Data Present": any(m["HasPixelData"] for m in metadata_list),
            "Zero Pixel Slices": self.detect_zero_pixel_slices(metadata_list),
        }

        for check, passed in checks.items():
            if not passed:
                self.logger.warning(f"Validation failed: {check}")
            else:
                self.logger.info(f"Validation passed: {check}")

        return all(checks.values())

    def _check_single_series(self, metadata_list: List[Dict[str, Any]]) -> bool:
        """Check if the DICOM files belong to the same series.

        :param List[Dict[str, Any]] metadata_list: Metadata of files.
        :return bool: True if files belong to the same series.
        """
        series_uids = {m["SeriesInstanceUID"] for m in metadata_list if m["SeriesInstanceUID"]}
        return len(series_uids) == 1

    def _check_equal_z_spacing(self, metadata_list: List[Dict[str, Any]]) -> bool:
        """Check if all slices are equally sapced.

        :param List[Dict[str, Any]] metadata_list: Metadata of files.
        :return bool: True if slices are equally spaced.
        """
        z_positions = [m["ZPosition"] for m in metadata_list if m["ZPosition"] is not None]
        if len(z_positions) < 2:
            return False
        z_positions_sorted = sorted(z_positions)
        spacings = [
            round(z_positions_sorted[i + 1] - z_positions_sorted[i], 5) for i in range(len(z_positions_sorted) - 1)
        ]
        return len(set(spacings)) == 1

    def _check_missing_slices(self, metadata_list: List[Dict[str, Any]]) -> bool:
        """Check for missing slices.

        :param List[Dict[str, Any]] metadata_list: Metadata of files.
        :return bool: True if no slices are missing.
        """
        instance_numbers = [m["InstanceNumber"] for m in metadata_list if m["InstanceNumber"] is not None]
        if not instance_numbers:
            self.logger.warning("No valid instance numbers found.")
            return False

        expected = set(range(1, max(instance_numbers) + 1))
        missing = expected - set(instance_numbers)
        if missing:
            self.logger.warning(f"Missing instance numbers: {sorted(missing)}")
            return False
        return True

    def _find_inconsistent_z_spacing(self, z_positions: List[float]) -> List[float]:
        """Find inconsistant Z Spacing.

        :param List[float] z_positions: Z Positions of slices.
        :return List[float]: Inconsistant Z positions.
        """
        sorted_positions = sorted(z_positions)
        differences = [
            round(sorted_positions[i + 1] - sorted_positions[i], 10) for i in range(len(sorted_positions) - 1)
        ]
        if not differences:
            return []
        most_common_diff = Counter(differences).most_common(1)[0][0]
        inconsistent_positions = [sorted_positions[i] for i, diff in enumerate(differences) if diff != most_common_diff]
        return inconsistent_positions

    def _check_metadata_consistency(self, metadata_list: List[Dict[str, Any]]) -> bool:
        """Check metadata consistency.

        :param List[Dict[str, Any]] metadata_list: Metadata of files.
        :return bool: True if metadata is consistent.
        """
        fields_to_check = [
            "Modality",
            "PixelSpacing",
            "SliceThickness",
            "ImageOrientationPatient",
            "PatientID",
            "StudyInstanceUID",
        ]
        inconsistent = {}
        for field in fields_to_check:
            values = {m[field] for m in metadata_list if m[field] is not None}
            if len(values) > 1:
                inconsistent[field] = values

        if inconsistent:
            for field, values in inconsistent.items():
                self.logger.warning(f"Inconsistent {field}: {values}")
            return False
        return True

    def detect_zero_pixel_slices(self, metadata_list: List[Dict[str, Any]]) -> bool:
        """Detect slices with all pixel values = 0.

        :param List[Dict[str, Any]] metadata_list: Metadata of files.
        :return bool: True if all slices have valid pixel data.
        """
        # Sort by Z-position
        sorted_slices = sorted(
            [m for m in metadata_list if m["ZPosition"] is not None], key=lambda x: x["ZPosition"], reverse=True
        )
        total_slices = len(sorted_slices)
        all_valid = True

        for idx, slice_info in enumerate(sorted_slices, start=1):
            try:
                dicom = pydicom.dcmread(slice_info["FilePath"], force=True)
                pixel_array = dicom.pixel_array
                if np.all(pixel_array == 0):
                    self.logger.warning(
                        f"Slice InstanceNumber {slice_info['InstanceNumber']}, "
                        f"({idx}-th of {total_slices}): all-zero pixel data."
                    )
                    all_valid = False
            except Exception as e:
                self.logger.warning(f"Failed to read pixel data for {slice_info['FilePath']}: {e}")
                all_valid = False

        return all_valid

    @staticmethod
    def find_missing_positions(ct_files: Union[List[Union[str, Path]], Path]) -> List[float]:
        """Identifies missing slices in a CT series by comparing slice positions.

        :param Union[List[Union[str, Path]], Path] ct_files: List of CT file paths or a directory containing the CT
        series files.
        :return List[float]: List of Z-positions with inconsistent spacing. Empty if spacing is consistent.
        """
        if isinstance(ct_files, (str, Path)):
            ct_files = sorted(Path(ct_files).glob("*.dcm"))

        slice_data = []
        for file_path in ct_files:
            try:
                dicom = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
                instance_number = getattr(dicom, "InstanceNumber", None)
                z_position = getattr(dicom, "ImagePositionPatient", [None, None, None])[2]
                slice_data.append((instance_number, z_position))
            except Exception:
                continue  # Skip unreadable files

        slice_data = [x for x in slice_data if x[0] is not None and x[1] is not None]

        if not slice_data:
            return []

        # Check for inconsistent Z-spacing
        slice_data.sort(key=lambda x: x[1])
        z_positions = [i[1] for i in slice_data]
        return ImageValidator.check_equal_differences(z_positions)

    @staticmethod
    def find_missing_slices(ct_files: Union[List[Union[str, Path]], Path]) -> List[float]:
        """Identifies missing slices in a CT series by comparing instance numbers.

        :param Union[List[Union[str, Path]], Path] ct_files: List of CT file paths or a directory containing the CT
        series files.
        :return List[float]: List of missing slice instance numbers. Empty if spacing is consistent.
        """
        if isinstance(ct_files, (str, Path)):
            ct_files = sorted(Path(ct_files).glob("*.dcm"))

        slice_data = []
        for file_path in ct_files:
            try:
                dicom = pydicom.dcmread(file_path, stop_before_pixels=True, force=True)
                instance_number = getattr(dicom, "InstanceNumber", None)
                z_position = getattr(dicom, "ImagePositionPatient", [None, None, None])[2]
                slice_data.append((instance_number, z_position))
            except Exception:
                continue  # Skip unreadable files

        slice_data = [x for x in slice_data if x[0] is not None and x[1] is not None]

        if not slice_data:
            return []

        # Check for missing instance numbers
        slice_data.sort(key=lambda x: x[0])
        given_instances = set(i[0] for i in slice_data)
        expected_instances = set(range(1, max(given_instances) + 1))
        missing_instances = list(expected_instances - given_instances)

        return missing_instances

    @staticmethod
    def check_equal_differences(z_positions: List[float]) -> List[float]:
        """Checks if the Z-axis positions are equally spaced.

        :param List[float] z_positions: List of Z-axis positions.
        :return List[float]: List of Z-positions where spacing deviates from the majority spacing.
        """
        sorted_positions = sorted(z_positions)
        differences = [
            round(sorted_positions[i + 1] - sorted_positions[i], 10) for i in range(len(sorted_positions) - 1)
        ]

        if not differences:
            return []

        most_common_diff = Counter(differences).most_common(1)[0][0]
        inconsistent_positions = [sorted_positions[i] for i, diff in enumerate(differences) if diff != most_common_diff]

        return inconsistent_positions
