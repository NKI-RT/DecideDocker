"""RTSTRUCT Modality related tools."""

import logging
from pathlib import Path
from typing import Dict, List, Union

import numpy as np
import pydicom
import SimpleITK as sitk
from scipy.ndimage import binary_fill_holes
from skimage.draw import polygon

from decide.utils.logger import setup_logger


class RTStruct:
    """RTSTRUCT class for all RTSTRUCT modality-related tools."""

    def __init__(
        self,
        rtstruct_path: Union[Path, str],
        referenced_image_path: Union[str, List[str], Path] = None,
        logger: logging.Logger = None,
    ):
        """
        Initialize the RTStruct object.

        :param rtstruct_path: Path to the RTSTRUCT DICOM file or a directory containing it.
        :param referenced_image_path: Path to the referenced image (DICOM folder, list of files, or NIfTI file),
        defaults to None.
        :param logger: Optional logger object, defaults to a new logger with INFO level.
        :raises FileNotFoundError: If the RTSTRUCT path does not exist or no DICOM file is found in the directory.
        :raises IOError: If the RTSTRUCT file cannot be read.
        """
        self.logger = logger or setup_logger(level=logging.INFO)

        rtstruct_path = Path(rtstruct_path)

        if not rtstruct_path.exists():
            raise FileNotFoundError(f"RTSTRUCT path does not exist: {rtstruct_path}")

        if rtstruct_path.is_dir():
            dcm_files = sorted(rtstruct_path.glob("*.dcm"))
            if not dcm_files:
                raise FileNotFoundError(f"No DICOM files found in directory: {rtstruct_path}")
            self.rtstruct_path = dcm_files[0]
            self.logger.info(f"Using first DICOM file from directory: {self.rtstruct_path}")
        else:
            self.rtstruct_path = rtstruct_path

        try:
            self.rtstruct = pydicom.dcmread(self.rtstruct_path)
            self.logger.info(f"Loaded RTSTRUCT from {self.rtstruct_path}")
        except Exception as e:
            self.logger.error(f"Failed to read RTSTRUCT file: {e}")
            raise IOError(f"Failed to read RTSTRUCT file: {e}")

        self.roi_dict = {
            roi.get("ROIName"): (indx, roi.get("ROINumber"))
            for indx, roi in enumerate(self.rtstruct.get("StructureSetROISequence", []))
        }

        self.referenced_image = None
        if referenced_image_path:
            self.set_reference_image(referenced_image_path)

    def set_reference_image(self, referenced_image_path: Union[str, List[str], Path]) -> None:
        """Set the reference image for the RTSTRUCT.

        :param Union[str, List[str], Path] referenced_image_path: Path to the referenced image (DICOM directory,
        list of files, or NIfTI file).
        :fixlater Exception: If the reference image cannot be loaded.
        """
        try:
            if isinstance(referenced_image_path, list):
                self._set_dicom_reference(referenced_image_path)
            elif isinstance(referenced_image_path, (str, Path)):
                path = Path(referenced_image_path)
                if path.is_dir():
                    self._set_dicom_reference(path)
                else:
                    self.referenced_image = sitk.ReadImage(str(path))
                    self.logger.info(f"Loaded referenced image from {path}")
        except Exception as e:
            self.logger.error(f"Failed to set reference image: {e}")
            raise

    def _set_dicom_reference(self, referenced_image_path: Union[str, Path, List[str]]) -> None:
        """Load a DICOM series as the reference image.

        :param Union[str, Path, List[str]] referenced_image_path: Path to the DICOM directory or list of DICOM files.
        :fixlater Exception:  If the DICOM series cannot be loaded.
        """
        reader = sitk.ImageSeriesReader()
        try:
            if isinstance(referenced_image_path, list):
                dicom_files = [str(Path(f)) for f in referenced_image_path]
            else:
                dicom_files = reader.GetGDCMSeriesFileNames(str(referenced_image_path))
            reader.SetFileNames(dicom_files)
            self.referenced_image = reader.Execute()
            self.logger.info("Referenced DICOM image loaded successfully.")
        except Exception as e:
            self.logger.error(f"Error loading DICOM reference image: {e}")
            raise

    def _load_metadata(self) -> None:
        """Load metadata from the referenced image including spacing, origin, direction, and image size."""
        self.spacing = self.referenced_image.GetSpacing()
        self.origin = self.referenced_image.GetOrigin()
        self.direction = self.referenced_image.GetDirection()
        self.image_size = self.referenced_image.GetSize()

    def get_binary_mask(self, roi_name: str, *, fill_holes: bool = False) -> Union[sitk.Image, bool]:
        """Generate a binary mask for a specified ROI.

        :param str roi_name: Name of the ROI to extract.
        :param bool fill_holes: Whether to fill holes in the mask., defaults to False
        :return Union[sitk.Image, bool]: Binary mask as a SimpleITK image, or False if reference image is not set.
        :raises ValueError: If the ROI name is not found in the RTSTRUCT.
        """
        if self.referenced_image:
            self._load_metadata()
            return self._make_binary_mask(roi_name, fill_holes)
        else:
            self.logger.warning("Referenced image not set. Please provide a DICOM or NIfTI image.")
            return False

    def _make_binary_mask(self, roi_name: str, *, fill_holes: bool = False) -> sitk.Image:
        """Create a binary mask for a specified ROI from RTSTRUCT, following Plastimatch's approach.

        :param str roi_name: Name of the ROI to convert to a binary mask.
        :param bool fill_holes: Whether to fill holes in positive contours., defaults to False
        :raises ValueError: If the ROI name is not found in the RTSTRUCT.
        :return sitk.Image: Binary mask of the ROI with proper metadata.
        """
        mask_array = np.zeros(self.image_size[::-1], dtype=np.uint8)

        if roi_name not in self.roi_dict:
            raise ValueError(f"ROI '{roi_name}' not found in ROI dictionary")

        roi_idx = self.roi_dict[roi_name][0]

        try:
            roi_contour = self.rtstruct.ROIContourSequence[roi_idx]
        except (AttributeError, IndexError):
            self.logger.warning(f"No contour sequence found for ROI '{roi_name}'")
            return self._empty_mask(mask_array)

        if not hasattr(roi_contour, "ContourSequence"):
            self.logger.warning(f"ROI '{roi_name}' has no ContourSequence")
            return self._empty_mask(mask_array)

        slice_contours = {}

        for contour in roi_contour.ContourSequence:
            if not hasattr(contour, "ContourData") or len(contour.ContourData) < 6:
                continue

            contour_data = np.array(contour.ContourData).reshape(-1, 3)
            z_position = float(contour_data[0, 2])
            slice_idx = int(round((z_position - self.origin[2]) / self.spacing[2]))

            if slice_idx < 0 or slice_idx >= self.image_size[2]:
                continue

            if slice_idx not in slice_contours:
                slice_contours[slice_idx] = []

            is_sub = hasattr(contour, "ContourStatus") and contour.ContourStatus == "SUB"
            contour_type = getattr(contour, "ContourGeometricType", "CLOSED_PLANAR")

            slice_contours[slice_idx].append({"data": contour_data, "is_sub": is_sub, "type": contour_type})

        for slice_idx, contours in slice_contours.items():
            slice_mask = np.zeros(self.image_size[:2], dtype=np.uint8)

            for contour_info in contours:
                contour_data = contour_info["data"]
                is_sub = contour_info["is_sub"]
                contour_type = contour_info["type"]

                x_coords = (contour_data[:, 0] - self.origin[0]) / self.spacing[0]
                y_coords = (contour_data[:, 1] - self.origin[1]) / self.spacing[1]

                if len(x_coords) >= 3:
                    if contour_type == "CLOSED_PLANAR" and not np.allclose(contour_data[0], contour_data[-1]):
                        x_coords = np.append(x_coords, x_coords[0])
                        y_coords = np.append(y_coords, y_coords[0])

                    rr, cc = polygon(y_coords, x_coords, shape=self.image_size[:2])

                    if is_sub:
                        slice_mask[rr, cc] = 0
                    else:
                        slice_mask[rr, cc] = 1

            if np.any(slice_mask) and fill_holes:
                slice_mask = binary_fill_holes(slice_mask).astype(np.uint8)

            mask_array[slice_idx] = slice_mask

        mask_sitk = sitk.GetImageFromArray(mask_array)
        mask_sitk.CopyInformation(self.referenced_image)
        return mask_sitk

    def _empty_mask(self, mask_array: np.ndarray) -> sitk.Image:
        """Create an empty mask image with the same metadata as the referenced image.

        :param np.ndarray mask_array: Empty mask array.
        :return sitk.Image: Empty SimpleITK image with copied metadata.
        """
        empty_mask = sitk.GetImageFromArray(mask_array)
        empty_mask.CopyInformation(self.referenced_image)
        return empty_mask

    def get_save_binary_mask(
        self, roi_name: str, output_filepath: Union[str, Path], *, fill_holes: bool = False, prune_empty: bool = True
    ) -> bool:
        """Generate a binary mask for a specified ROI and save it to a file.

        :param str roi_name: Name of the ROI to extract.
        :param Union[str, Path] output_filepath: Path to save the binary mask image (.nii.gz).
        :param bool fill_holes: Whether to fill holes in the mask., defaults to False
        :param bool prune_empty: If True, raises an error for empty masks. If False, saves with a warning.
        defaults to True
        :raises ValueError: If the ROI name is not found or the mask is empty and prune_empty is True.
        :fixlater Exception: If saving the image fails.
        :return bool: True if the mask was successfully saved, False otherwise.
        """
        try:
            mask = self.get_binary_mask(roi_name, fill_holes)
            if isinstance(mask, sitk.Image):
                array = sitk.GetArrayFromImage(mask)
                if not np.any(array):
                    if prune_empty:
                        raise ValueError(f"Mask for ROI '{roi_name}' is empty and prune_empty=True.")
                    else:
                        self.logger.warning(
                            f"Mask for ROI '{roi_name}' is empty. Saved anyway due to prune_empty=False."
                        )
                output_path = Path(output_filepath)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                sitk.WriteImage(mask, str(output_path))
                self.logger.info(f"Saved binary mask for ROI '{roi_name}' to {output_path}")
                return True
            else:
                self.logger.error("Failed to generate binary mask. Referenced image may be missing.")
                return False
        except Exception as e:
            self.logger.error(f"Error saving binary mask for ROI '{roi_name}': {e}")
            return False

    def prune_rtstruct_rois(self, rois_to_keep: List[str]) -> None:
        """Filter the RTSTRUCT to keep only the specified ROIs.

        :param List[str] rois_to_keep: List of ROI names to retain.
        :fixlater Exception: If pruning fails due to malformed RTSTRUCT.
        """
        try:
            roi_numbers_to_keep = []
            structure_set_roi_sequences_to_keep = []

            for roi_seq in self.rtstruct.StructureSetROISequence:
                if roi_seq.ROIName in rois_to_keep:
                    roi_numbers_to_keep.append(roi_seq.ROINumber)
                    structure_set_roi_sequences_to_keep.append(roi_seq)

            roi_contour_sequences_to_keep = []
            if hasattr(self.rtstruct, "ROIContourSequence"):
                for roi_contour_seq in self.rtstruct.ROIContourSequence:
                    if roi_contour_seq.ReferencedROINumber in roi_numbers_to_keep:
                        roi_contour_sequences_to_keep.append(roi_contour_seq)

            self.rtstruct.StructureSetROISequence = pydicom.sequence.Sequence(structure_set_roi_sequences_to_keep)
            if roi_contour_sequences_to_keep:
                self.rtstruct.ROIContourSequence = pydicom.sequence.Sequence(roi_contour_sequences_to_keep)
            elif hasattr(self.rtstruct, "ROIContourSequence"):
                del self.rtstruct.ROIContourSequence

            if hasattr(self.rtstruct, "RTROIObservationsSequence"):
                filtered_rt_observations = [
                    obs
                    for obs in self.rtstruct.RTROIObservationsSequence
                    if obs.ReferencedROINumber in roi_numbers_to_keep
                ]
                self.rtstruct.RTROIObservationsSequence = pydicom.sequence.Sequence(filtered_rt_observations)

            self.roi_dict = {
                roi.get("ROIName"): (indx, roi.get("ROINumber"))
                for indx, roi in enumerate(self.rtstruct.get("StructureSetROISequence", []))
            }

            self.logger.info(f"Pruned RTSTRUCT to keep ROIs: {rois_to_keep}")
        except Exception as e:
            self.logger.error(f"Error pruning RTSTRUCT ROIs: {e}")
            raise

    def rename_rois(self, rename_map: Dict[str, str]) -> None:
        """Rename ROIs in the RTSTRUCT based on a mapping.

        :param Dict[str, str] rename_map: Dictionary mapping old ROI names to new names.
        :fixlater Exception: If renaming fails due to malformed RTSTRUCT.
        """
        try:
            for roi in self.rtstruct.get("StructureSetROISequence", []):
                if roi.ROIName in rename_map:
                    old_name = roi.ROIName
                    roi.ROIName = rename_map[old_name]
                    self.logger.info(f"Renamed ROI '{old_name}' to '{roi.ROIName}'")
        except Exception as e:
            self.logger.error(f"Error renaming ROIs: {e}")
            raise

    def validate_roi(self, roi_name: str) -> bool:
        """Validate whether the contours of the specified ROI are equally spaced along the Z-axis.

        :param str roi_name: Name of the ROI to validate.
        :raises ValueError: True if Z-values are equally spaced, False otherwise.
        :raises ValueError: If the ROI name is not found or has no contour data.
        :return bool:
        """
        if roi_name not in self.roi_dict:
            raise ValueError(f"ROI '{roi_name}' not found in RTSTRUCT.")

        roi_index, roi_number = self.roi_dict[roi_name]
        contour_sequence = self.rtstruct.get("ROIContourSequence", [])[roi_index].get("ContourSequence", [])

        if not contour_sequence:
            raise ValueError(f"No contour data found for ROI '{roi_name}'.")

        z_values = []
        for contour in contour_sequence:
            coords = contour.get("ContourData", [])
            if coords:
                # Assuming each contour is a closed polygon in one plane
                z_values.append(coords[2])  # Z-value of the first point

        if len(z_values) < 2:
            return True  # Not enough data to determine spacing
        z_values_sorted = sorted(z_values)
        spacings = [round(z_values_sorted[i + 1] - z_values_sorted[i], 5) for i in range(len(z_values_sorted) - 1)]
        spacing_set = set(spacings)

        return len(spacing_set) == 1

    def save_rtstruct(self, output_filepath: Union[str, Path]) -> None:
        """
        Save the modified RTSTRUCT to a file.

        :param Union[str, Path] output_filepath: Path to save the RTSTRUCT DICOM file.
        :raises IOError: If saving fails due to file system issues.
        """
        try:
            self.rtstruct.save_as(str(output_filepath))
            self.logger.info(f"Saved RTSTRUCT to {output_filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save RTSTRUCT: {e}")
            raise IOError(f"Failed to save RTSTRUCT to '{output_filepath}': {e}")
