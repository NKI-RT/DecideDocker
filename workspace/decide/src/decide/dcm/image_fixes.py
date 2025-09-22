"""Fix / Modify Images."""

import logging

import numpy as np
import SimpleITK as sitk


def interpolate_missing_slices(input_path: str, output_path: str, logger: logging.Logger = None):
    """Interpolates a missing slice between two slices of a nifit binary image.

    :param str input_path: nifti image (binary)
    :param str output_path: output image
    :param logging.Logger logger: Optional Logger Object, defaults to None
    """
    # Set up logger
    if logger is None:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("SliceInterpolator")

    # Read the image
    image = sitk.ReadImage(str(input_path))
    array = sitk.GetArrayFromImage(image)  # shape: [slices, height, width]

    modified = False

    # Identify slices with no '1' values
    for i in range(1, array.shape[0] - 1):
        if np.all(array[i] == 0):
            if np.any(array[i - 1] == 1) and np.any(array[i + 1] == 1):
                # Perform linear interpolation
                array[i] = (array[i - 1].astype(np.float32) + array[i + 1].astype(np.float32)) / 2
                array[i] = (array[i] > 0.5).astype(np.uint8)  # Convert back to binary mask
                modified = True
                logger.debug(f"Slice {i} was interpolated.")

    if modified:
        logger.info(f"Image was modified. Saving corrected image {input_path}.")
    else:
        logger.info(f"No modifications were necessary. Saving original image {input_path}.")

    # Convert back to SimpleITK image
    corrected_image = sitk.GetImageFromArray(array)
    corrected_image.CopyInformation(image)  # Preserve metadata

    # Save the modified image
    sitk.WriteImage(corrected_image, str(output_path))
