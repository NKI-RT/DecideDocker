"""Module for Post-processing of Autosegmented Thoracic Structures."""

# Essentials
import os
import warnings
from pathlib import Path

# Typing
from typing import Any, Dict, List, Optional, Union

import SimpleITK as sitk


class MaskPostProcessor:
    """Static methods for all mask postprocessing."""

    @staticmethod
    def remove_islands_thr(
        input_data: Union[sitk.Image, str, Path], output_path: Optional[Union[str, Path]] = None, thr: float = 0.3
    ) -> Optional[sitk.Image]:
        """Removes small islands (disconnected components) from a binary mask based on a volume threshold.

        This function identifies connected components in a binary mask and removes those with
        volumes smaller than a specified percentage of the largest component's volume.

        :param Union[sitk.Image, str, Path] input_data: Either a path to the input .nii.gz file
            or a SimpleITK image object. Must be a binary mask (0s and 1s).
        :param Optional[Union[str, Path]] output_path: Path to save the modified .nii.gz file.
        If None, returns the image., defaults to None
        :param float thr: A value between 0 and 1 (default=0.3). Components with volume less than
            this fraction of the largest component's volume will be removed., defaults to 0.3
        :raises ValueError: If thr is not between 0 and 1 or if input image is not binary.
        :raises FileNotFoundError: If the input file doesn't exist.
        :raises IOError: If there's an error reading the input file or writing the output file.
        :raises Exception: For any other error.
        :return Optional[sitk.Image]: SimpleITK image if output_path is None, otherwise None after saving to file.
        """
        # Validate threshold parameter
        if not 0 <= thr <= 1:
            raise ValueError(f"Threshold must be between 0 and 1, got {thr}")

        try:
            # Handle input: either file path or SimpleITK image
            if isinstance(input_data, (str, Path)):
                if not os.path.exists(input_data):
                    raise FileNotFoundError(f"Input file not found: {input_data}")

                try:
                    image = sitk.ReadImage(input_data)
                except Exception as e:
                    raise IOError(f"Error reading input file: {e}")
            else:
                image = input_data

            # Ensure the image is binary
            binary_check = sitk.BinaryThreshold(
                image, lowerThreshold=0.5, upperThreshold=1.5, insideValue=1, outsideValue=0
            )
            if not sitk.Equal(image, binary_check):
                image = binary_check

            # Use ConnectedComponent to find isolated regions
            connected_components = sitk.ConnectedComponent(image)

            # Use LabelShapeStatisticsImageFilter to get volumes
            label_stats = sitk.LabelShapeStatisticsImageFilter()
            label_stats.Execute(connected_components)

            # Get all labels and their physical volumes
            labels = label_stats.GetLabels()

            # Handle empty mask case
            if not labels:
                if output_path:
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    sitk.WriteImage(image, output_path)
                    return None
                return image

            volumes = [label_stats.GetPhysicalSize(label) for label in labels]

            # Find the largest segment volume
            max_volume = max(volumes)
            volume_threshold = max_volume * thr

            # Identify valid labels (those meeting the threshold)
            valid_labels = [label for label, volume in zip(labels, volumes) if volume >= volume_threshold]

            # Create a binary mask containing only valid segments
            result_image = sitk.Image(image.GetSize(), sitk.sitkUInt8)
            result_image.CopyInformation(image)

            # Add each valid component to the result image
            for label in valid_labels:
                # Extract the binary mask for this label
                label_mask = sitk.Equal(connected_components, label)
                # Add it to the result
                result_image = sitk.Or(result_image, label_mask)

            # Save or return the result
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    sitk.WriteImage(result_image, output_path)
                except Exception as e:
                    raise IOError(f"Error writing output file: {e}")
                return None
            else:
                return result_image

        except Exception as e:
            # Re-raise with the original error type
            if isinstance(e, (FileNotFoundError, IOError, ValueError)):
                raise e
            else:
                # For any other exceptions, re-raise as a generic error
                warnings.warn(f"An error occurred: {e}")

    @staticmethod
    def combine_binary_masks(
        input_data: List[Union[sitk.Image, str, Path]],
        output_path: Optional[Union[str, Path]] = None,
        **kwargs: Dict[str, Any],
    ) -> Optional[sitk.Image]:
        """Combines multiple binary masks into a single mask using only SimpleITK operations.

        :param List[Union[sitk.Image, str, Path]] input_data: List of binary masks,
        either as paths to .nii.gz files or SimpleITK image objects.
        :param Optional[Union[str, Path]] output_path: Path to save the combined .nii.gz file.
        If None, returns the image instead., defaults to None
        :raises ValueError: If input_data is empty.
        :raises FileNotFoundError: If input file don't exist.
        :raises IOError: If file can not be read, or can not write the output file.
        :raises RuntimeError: if the image has inconsistent dimensions or metadata compared to the reference image.
        :return Optional[sitk.Image]: SimpleITK image if output_path is None, otherwise None after saving to file.
        """
        if not input_data:
            raise ValueError("Input list cannot be empty")

        try:
            # Track the original reference image for metadata preservation
            reference_image = None

            # Process each input image
            for idx, item in enumerate(input_data):
                # Track filename for better error messages
                filename = str(item) if isinstance(item, (str, Path)) else f"In-memory image {idx}"

                # Load the image
                if isinstance(item, (str, Path)):
                    if not os.path.exists(item):
                        raise FileNotFoundError(f"Input file not found: {filename}")
                    try:
                        image = sitk.ReadImage(str(item))
                    except Exception as e:
                        raise IOError(f"Error reading input file {filename}: {e}")
                else:
                    image = item

                # Store the first image as reference
                if idx == 0:
                    reference_image = image
                    # Initialize result as a copy of the first image
                    result_image = sitk.Cast(image, sitk.sitkUInt8)

                    # Skip empty first image
                    stats = sitk.StatisticsImageFilter()
                    stats.Execute(image)
                    if stats.GetSum() == 0:
                        warnings.warn(f"First mask {filename} is empty. Skipping this mask.")
                        continue

                    continue

                # Ensure consistent dimensions with reference image
                if (
                    image.GetSize() != reference_image.GetSize()
                    or image.GetSpacing() != reference_image.GetSpacing()
                    or image.GetOrigin() != reference_image.GetOrigin()
                    or image.GetDirection() != reference_image.GetDirection()
                ):
                    raise RuntimeError(
                        f"Image {filename} has inconsistent dimensions or metadata compared to the reference image."
                    )

                # Skip empty masks
                stats = sitk.StatisticsImageFilter()
                stats.Execute(image)
                if stats.GetSum() == 0:
                    warnings.warn(f"Mask {filename} is empty. Skipping this mask.")
                    continue

                # Combine with result using OR operation
                result_image = sitk.Or(result_image, sitk.Cast(image, sitk.sitkUInt8))

            # Check if we have a valid result (we might not if all masks were empty)
            if "result_image" not in locals():
                warnings.warn("All provided masks were empty. Creating an empty mask.")
                result_image = sitk.Image(reference_image.GetSize(), sitk.sitkUInt8)
                result_image.CopyInformation(reference_image)

            # Make sure we preserve all metadata from the original reference image
            result_image.CopyInformation(reference_image)

            # Save or return the result
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    # Ensure we're saving with the correct compression and format
                    sitk.WriteImage(result_image, str(output_path), True)  # True enables compression
                except Exception as e:
                    raise IOError(f"Error writing output file {output_path}: {e}")
                return None
            else:
                return result_image

        except Exception:
            # Re-raise with the original error type
            raise

    @staticmethod
    def remove_overlapping_parts(
        mask_1: Union[sitk.Image, str, Path],
        mask_2: Union[sitk.Image, str, Path],
        output_path: Optional[Union[str, Path]] = None,
        **kwargs: Dict[str, Any],
    ) -> Optional[sitk.Image]:
        """Remove the overlapping parts from mask_1 that overlap with mask_2.

        This function performs a subtraction operation,
        removing areas from the first mask where they overlap with the second mask.

        :param Union[sitk.Image, str, Path] mask_1: The first binary mask as a SimpleITK Image or a file path.
        :param Union[sitk.Image, str, Path] mask_2: The second binary mask as a SimpleITK Image or a file path.
        :param Optional[Union[str, Path]] output_path: The file path to save the resulting mask.
        If None, the result is returned as a SimpleITK Image, defaults to None
        :raises FileNotFoundError:  If any input file doesn't exist.
        :raises IOError:  If there's an error reading input files or writing the output file.
        :raises RuntimeError:  If input images have inconsistent dimensions or metadata.
        :return Optional[sitk.Image]: SimpleITK image if output_path is None, otherwise None after saving to file.
        """
        try:
            # Track filenames for better error messages
            mask_1_name = str(mask_1) if isinstance(mask_1, (str, Path)) else "First in-memory image"
            mask_2_name = str(mask_2) if isinstance(mask_2, (str, Path)) else "Second in-memory image"

            # Load the binary masks if they are given as paths
            if isinstance(mask_1, (str, Path)):
                if not os.path.exists(mask_1):
                    raise FileNotFoundError(f"First mask file not found: {mask_1_name}")
                try:
                    mask_1 = sitk.ReadImage(str(mask_1))
                except Exception as e:
                    raise IOError(f"Error reading first mask file {mask_1_name}: {e}")

            if isinstance(mask_2, (str, Path)):
                if not os.path.exists(mask_2):
                    raise FileNotFoundError(f"Second mask file not found: {mask_2_name}")
                try:
                    mask_2 = sitk.ReadImage(str(mask_2))
                except Exception as e:
                    raise IOError(f"Error reading second mask file {mask_2_name}: {e}")

            # Ensure consistent dimensions and metadata
            if (
                mask_1.GetSize() != mask_2.GetSize()
                or mask_1.GetSpacing() != mask_2.GetSpacing()
                or mask_1.GetOrigin() != mask_2.GetOrigin()
                or mask_1.GetDirection() != mask_2.GetDirection()
            ):
                raise RuntimeError(
                    f"Input masks have inconsistent dimensions or metadata: {mask_1_name} vs {mask_2_name}"
                )

            # Cast to UInt8 for consistency but don't apply thresholding
            mask_1_uint8 = sitk.Cast(mask_1, sitk.sitkUInt8)
            mask_2_uint8 = sitk.Cast(mask_2, sitk.sitkUInt8)

            # Check if either mask is empty
            stats_1 = sitk.StatisticsImageFilter()
            stats_1.Execute(mask_1_uint8)
            if stats_1.GetSum() == 0:
                warnings.warn(f"First mask {mask_1_name} is empty. Result will be empty.")

            stats_2 = sitk.StatisticsImageFilter()
            stats_2.Execute(mask_2_uint8)
            if stats_2.GetSum() == 0:
                warnings.warn(f"Second mask {mask_2_name} is empty. Result will be identical to first mask.")
                result_mask = mask_1_uint8
            else:
                # Remove the parts from mask_1 that overlap with mask_2
                # Invert mask_2 and perform logical AND
                inverted_mask_2 = sitk.BinaryNot(mask_2_uint8)
                result_mask = sitk.And(mask_1_uint8, inverted_mask_2)

            # Copy metadata from mask_1 to result_mask
            result_mask.CopyInformation(mask_1)

            # Save the result if output_path is provided, else return the result
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    sitk.WriteImage(result_mask, str(output_path), True)  # Enable compression
                except Exception as e:
                    raise IOError(f"Error writing output file {output_path}: {e}")
                return None
            else:
                return result_mask

        except Exception:
            # Re-raise with the original error type
            raise
