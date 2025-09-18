"""Utilities."""

import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import SimpleITK as sitk

from decide.utils.logger import setup_logger


def generate_tree(target_dir: str, prefix: str = "", ignore: List = ["__pycache__"]) -> str:
    """Get the structure of a directory as a tree.

    :param str target_dir: The target directory.
    :param str prefix: Prefix for name in the tree, defaults to ""
    :param List ignore: Items to ignore, defaults to ["__pycache__"]
    :return str: The structure of a directory as a tree.
    """
    tree = ""
    contents = os.listdir(target_dir)
    for not_needed in ignore:
        if not_needed in contents:
            contents.remove(not_needed)
    pointers = ["├── "] * (len(contents) - 1) + ["└── "]

    for pointer, item in zip(pointers, contents):
        item_path = os.path.join(target_dir, item)
        tree += prefix + pointer + item + "\n"
        if os.path.isdir(item_path):
            extension = "│   " if pointer == "├── " else "    "
            tree += generate_tree(item_path, prefix + extension)

    return tree


def zip_files(filepaths: List, output_zip: str, logger: logging.Logger = None) -> bool:
    """Compress a list of file paths into a zip file.

    :param List filepaths: List of file paths to include in the zip file.
    :param str output_zip: Path to the output zip file.
    :param logging.Logger logger: Optional logger object, defaults to None
    :return bool: status
    """
    logger = logger if logger else setup_logger("Zip Logger")
    len_filepaths = len(filepaths)
    if len_filepaths:
        logger.info(f"Zipping {len_filepaths} files")
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for filepath in filepaths:
                filepath = Path(filepath)
                if filepath.exists():
                    arcname = filepath.name
                    zipf.write(filepath, arcname)
                else:
                    logger.warning(f"File not found - {filepath}")
        return True
    else:
        logger.warning(f"{len_filepaths} files to be zipped!")
        return False


def calculate_volume(image: Union[sitk.Image, str]) -> float:
    """Calculate the volume of a binary mask in a NIfTI file.

    :param Union[sitk.Image, str] image: The input image or the path to the NIfTI file.
    :return float: The total volume in cubic millimeters (mm^3).
    """
    # Load the image if a path is provided
    if isinstance(image, str):
        image = sitk.ReadImage(image)

    # Get the voxel size (in mm^3)
    voxel_size = np.prod(image.GetSpacing())

    # Convert the image to a numpy array
    data = sitk.GetArrayFromImage(image)

    # Calculate the total volume (in mm^3)
    total_volume = np.sum(data) * voxel_size

    return total_volume


def get_component_count(image: Union[sitk.Image, str, Path]) -> Tuple[int, List[float]]:
    """Count the number of connected components in a binary image and return their physical sizes.

    :param Union[sitk.Image, str, Path] image: The input image, path to the NIfTI file as string, or Path object.
    :return Tuple[int, List[float]]: A tuple containing:
        - The number of connected components in the image
        - A list of physical sizes (volumes in mm³) for each component
    """
    # Load the image if a path is provided
    if isinstance(image, (str, Path)):
        image = sitk.ReadImage(str(image))

    # Perform connected component analysis
    connected_components = sitk.ConnectedComponent(image)

    # Get label statistics
    label_shape_filter = sitk.LabelShapeStatisticsImageFilter()
    label_shape_filter.Execute(connected_components)

    # Get all labels
    labels = label_shape_filter.GetLabels()

    # Create a list of physical sizes for each label
    physical_sizes = [round(label_shape_filter.GetPhysicalSize(label), 1) for label in labels]

    # Return the count of components and their physical sizes
    return (len(labels), physical_sizes)


def move_files_to_directory(files: List[Union[str, Path]], dest_dir: Union[str, Path]) -> None:
    """
    Move specified files to a destination directory using shutil.move.

    :param files: List of file paths to move.
    :param dest_dir: Destination directory path.
    :raises FileExistsError: If the destination directory is not empty.
    :raises FileNotFoundError: If a file does not exist.
    :raises ValueError: If a path is not a file.
    :raises OSError: If the move operation fails.
    """
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    # Raise if destination directory is not empty
    if any(dest_path.iterdir()):
        raise FileExistsError(f"Destination directory '{dest_path}' is not empty.")

    for file in files:
        file_path = Path(file)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        target_path = dest_path / file_path.name
        try:
            shutil.move(str(file_path), str(target_path))
        except OSError as e:
            raise OSError(f"Failed to move {file_path} to {target_path}: {e}")


def copy_files_to_directory(files: List[Union[str, Path]], dest_dir: Union[str, Path]) -> None:
    """
    Copy specified files to a destination directory using shutil.copy2.

    :param files: List of file paths to copy.
    :param dest_dir: Destination directory path.
    :raises FileExistsError: If the destination directory is not empty.
    :raises FileNotFoundError: If a file does not exist.
    :raises ValueError: If a path is not a file.
    :raises OSError: If the copy operation fails.
    """
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    # Raise if destination directory is not empty
    if any(dest_path.iterdir()):
        raise FileExistsError(f"Destination directory '{dest_path}' is not empty.")

    for file in files:
        file_path = Path(file)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        target_path = dest_path / file_path.name
        try:
            shutil.copy2(file_path, target_path)
        except OSError as e:
            raise OSError(f"Failed to copy {file_path} to {target_path}: {e}")
