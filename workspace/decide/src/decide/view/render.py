"""Modeule for redereing 3D Binary (0|1) using matplotlib."""

import logging
from pathlib import Path
from typing import Literal, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import SimpleITK as sitk


class MaskRenderer3D:
    """Renders 3D binary masks using ray casting and 2D matplotlib.

    Works in headless Docker environments without graphics libraries.
    Supports multiple masks rendered together with depth-based occlusion.
    """

    # Default color palette (same order every time)
    DEFAULT_COLORS = [
        (1.0, 0.0, 0.0),  # Red
        (0.0, 1.0, 0.0),  # Green
        (0.0, 0.0, 1.0),  # Blue
        (1.0, 1.0, 0.0),  # Yellow
        (1.0, 0.0, 1.0),  # Magenta
        (0.0, 1.0, 1.0),  # Cyan
        (1.0, 0.5, 0.0),  # Orange
        (0.5, 0.0, 1.0),  # Purple
        (0.0, 1.0, 0.5),  # Teal
        (1.0, 0.0, 0.5),  # Pink
    ]

    def __init__(self, masks: Union[sitk.Image, list[sitk.Image]], *, verbose: bool = False):
        """Initialize renderer with one or more SimpleITK binary masks.

        :param Union[sitk.Image, list[sitk.Image]] masks: SimpleITK Image object or list of SimpleITK Image objects
        :param bool verbose: If True, print initialization information, defaults to False
        """
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

        # Set up logging
        if self.verbose and not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        elif not self.verbose:
            self.logger.setLevel(logging.WARNING)

        # Handle single mask or list of masks
        if not isinstance(masks, list):
            masks = [masks]

        self.masks = masks
        self.mask_arrays = []

        # Process all masks
        for idx, mask in enumerate(masks):
            # Convert to numpy array and transpose from (Z, Y, X) to (X, Y, Z)
            mask_array = sitk.GetArrayFromImage(mask)
            mask_array = np.ascontiguousarray(np.transpose(mask_array, (2, 1, 0)))
            self.mask_arrays.append(mask_array)

            # Get spacing and shape from first mask (assume all have same spacing)
            if idx == 0:
                self.spacing = mask.GetSpacing()
                self.shape = mask_array.shape

            self.logger.info(f"Mask {idx}: shape {mask_array.shape}, non-zero voxels: {np.sum(mask_array > 0)}")

        self.logger.info(f"Spacing (X, Y, Z): {self.spacing}")

    def render(
        self,
        directions: Union[
            Literal["anterior", "posterior", "left", "right", "superior", "inferior"],
            list[Literal["anterior", "posterior", "left", "right", "superior", "inferior"]],
        ] = "anterior",
        light_direction: Optional[Tuple[float, float, float]] = None,
        ambient: float = 0.4,
        diffuse: float = 0.8,
        figsize: Optional[Tuple[float, float]] = None,
        dpi: int = 100,
        background_color: Union[Literal["black", "white", "grey", "gray"], Tuple[float, float, float]] = "black",
        mask_colors: Optional[list[Tuple[float, float, float]]] = None,
        bound_color: Tuple[float, float, float] = (0.3, 0.5, 0.7),
        bound_alpha: float = 0.6,
        *,
        aspect_correct: bool = True,
        show_bounds: bool = True,
        save_path: Optional[Union[str, Path]] = None,
    ) -> Union[plt.Figure, list[plt.Figure]]:
        """Render the mask(s) from one or multiple viewing directions.

        :param Union[Literal, list] directions: Single direction or list of directions to render
        :param Optional[Tuple[float, float, float]] light_direction: Light direction as (x, y, z).
        If None, uses default for each view, defaults to None
        :param float ambient: Ambient light intensity (0-1), defaults to 0.4
        :param float diffuse: Diffuse light intensity (0-1), defaults to 0.8
        :param Optional[Tuple[float, float]] figsize: Figure size in inches.
        If None, computed from aspect ratio, defaults to None
        :param int dpi: Dots per inch for rendering, defaults to 100
        :param Union[Literal, Tuple[float, float, float]] background_color: "black", "white", "grey"/"gray",
        or RGB tuple (0-1 range), defaults to "black"
        :param Optional[list[Tuple[float, float, float]]] mask_colors: List of RGB tuples (0-1 range) for each mask.
        If None, uses default palette, defaults to None
        :param Tuple[float, float, float] bound_color: RGB color for bounding box, defaults to (0.3, 0.5, 0.7)
        :param float bound_alpha: Alpha transparency for bounding box (0-1), defaults to 0.6
        :param bool aspect_correct: If True, use correct aspect ratio based on spacing, defaults to True
        :param bool show_bounds: If True, draw bounding box of the image volume, defaults to True
        :param Optional[Union[str, Path]] save_path: If provided, save the figure(s) to this path.
        For multiple directions,will append direction name to filename (e.g., "output_anterior.png"), defaults to None
        :return Union[plt.Figure, list[plt.Figure]]: matplotlib Figure object or
        list of Figure objects (if multiple directions)
        """
        # Handle single or multiple directions
        if isinstance(directions, str):
            directions = [directions]
            return_single = True
        else:
            return_single = False

        # Set default colors if not provided
        if mask_colors is None:
            mask_colors = [self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)] for i in range(len(self.mask_arrays))]
        elif len(mask_colors) < len(self.mask_arrays):
            # Extend with default colors if not enough provided
            mask_colors = list(mask_colors) + [
                self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                for i in range(len(mask_colors), len(self.mask_arrays))
            ]

        figures = []
        for direction in directions:
            fig = self._render_single_direction(
                direction=direction,
                light_direction=light_direction,
                ambient=ambient,
                diffuse=diffuse,
                figsize=figsize,
                dpi=dpi,
                background_color=background_color,
                mask_colors=mask_colors,
                bound_color=bound_color,
                bound_alpha=bound_alpha,
                save_path=save_path,
                aspect_correct=aspect_correct,
                show_bounds=show_bounds,
                multiple_directions=len(directions) > 1,
            )
            figures.append(fig)

        return figures[0] if return_single else figures

    def _render_single_direction(
        self,
        direction: str,
        light_direction: Optional[Tuple[float, float, float]],
        ambient: float,
        diffuse: float,
        figsize: Optional[Tuple[float, float]],
        dpi: int,
        background_color: Union[str, Tuple[float, float, float]],
        mask_colors: list[Tuple[float, float, float]],
        bound_color: Tuple[float, float, float],
        bound_alpha: float,
        save_path: Optional[Union[str, Path]],
        *,
        aspect_correct: bool,
        show_bounds: bool,
        multiple_directions: bool,
    ) -> plt.Figure:
        """Render a single direction."""
        self.logger.info(f"Rendering from {direction} direction...")

        # Set default light direction for this view
        if light_direction is None:
            current_light_direction = self._get_default_light_direction(direction)
        else:
            current_light_direction = np.array(light_direction, dtype=float)
        current_light_direction = current_light_direction / np.linalg.norm(current_light_direction)

        # Get view configuration
        view_config = self._get_view_config(direction)
        proj_shape = (self.shape[view_config["ax1"]], self.shape[view_config["ax2"]])

        # Ray cast all masks
        all_depths, all_normals, all_valid_masks = self._ray_cast_all_masks(direction)

        # Determine frontmost surface at each pixel
        frontmost_mask, frontmost_depth, frontmost_normal = self._compute_frontmost_surfaces(
            all_depths, all_normals, all_valid_masks, proj_shape
        )

        # Render the final image
        final_image = self._render_final_image(
            frontmost_mask,
            frontmost_depth,
            frontmost_normal,
            current_light_direction,
            ambient,
            diffuse,
            mask_colors,
            background_color,
        )

        # Create figure
        fig = self._create_figure(
            image=final_image,
            direction=direction,
            figsize=figsize,
            dpi=dpi,
            aspect_correct=aspect_correct,
            background_color=background_color,
            show_bounds=show_bounds,
            bound_color=bound_color,
            bound_alpha=bound_alpha,
        )

        # Save figure if path provided
        if save_path is not None:
            save_path = Path(save_path)

            # If multiple directions, append direction name to filename
            if multiple_directions:
                stem = save_path.stem
                suffix = save_path.suffix
                parent = save_path.parent
                save_file = parent / f"{stem}_{direction}{suffix}"
            else:
                save_file = save_path

            # Get background color for saving
            bg_color = self._parse_background_color(background_color)
            bg_color_mpl = tuple(bg_color) if isinstance(bg_color, np.ndarray) else bg_color

            fig.savefig(save_file, dpi=dpi, bbox_inches="tight", pad_inches=0, facecolor=bg_color_mpl)

            self.logger.info(f"Figure saved to: {save_file}")

            # Close the figure to avoid display
            plt.close(fig)

        return fig

    def _parse_background_color(self, background_color: Union[str, Tuple[float, float, float]]) -> np.ndarray:
        """Parse background color string or tuple to RGB array."""
        if isinstance(background_color, tuple):
            return np.array(background_color)

        color_map = {
            "black": np.array([0.0, 0.0, 0.0]),
            "white": np.array([1.0, 1.0, 1.0]),
            "grey": np.array([0.5, 0.5, 0.5]),
            "gray": np.array([0.5, 0.5, 0.5]),
        }

        return color_map.get(background_color.lower(), np.array([0.0, 0.0, 0.0]))

    def _get_view_config(self, direction: str) -> dict:
        """Get ray casting configuration for a view direction."""
        configs = {
            "anterior": {"ray_axis": 1, "ax1": 2, "ax2": 0, "forward": True},
            "posterior": {"ray_axis": 1, "ax1": 2, "ax2": 0, "forward": False},
            "right": {"ray_axis": 0, "ax1": 2, "ax2": 1, "forward": True},
            "left": {"ray_axis": 0, "ax1": 2, "ax2": 1, "forward": False},
            "superior": {"ray_axis": 2, "ax1": 1, "ax2": 0, "forward": False},
            "inferior": {"ray_axis": 2, "ax1": 1, "ax2": 0, "forward": True},
        }
        return configs[direction.lower()]

    def _get_default_light_direction(self, direction: str) -> np.ndarray:
        """Get default light direction based on view direction."""
        light_dirs = {
            "anterior": np.array([0.3, 0.7, 0.3]),
            "posterior": np.array([0.3, -0.7, 0.3]),
            "right": np.array([0.7, 0.3, 0.3]),
            "left": np.array([-0.7, 0.3, 0.3]),
            "superior": np.array([0.3, 0.3, 0.7]),
            "inferior": np.array([0.3, 0.3, -0.7]),
        }
        return light_dirs[direction.lower()]

    def _get_aspect_ratio(self, direction: str) -> float:
        """Calculate aspect ratio for the projection based on spacing."""
        view_axes = {
            "anterior": (2, 0),
            "posterior": (2, 0),
            "right": (2, 1),
            "left": (2, 1),
            "superior": (1, 0),
            "inferior": (1, 0),
        }
        vert_axis, horiz_axis = view_axes[direction.lower()]
        aspect_ratio = self.spacing[vert_axis] / self.spacing[horiz_axis]

        self.logger.info(f"  Aspect ratio: {aspect_ratio:.3f}")

        return aspect_ratio

    def _ray_cast_all_masks(self, direction: str) -> Tuple[list, list, list]:
        """Ray cast all masks and return depths, normals, and valid masks."""
        all_depths, all_normals, all_valid_masks = [], [], []

        for mask_idx, mask_array in enumerate(self.mask_arrays):
            self.logger.info(f"  Ray casting mask {mask_idx}...")

            depth_map, normal_map, valid_mask = self._ray_cast_single(mask_array, direction)
            all_depths.append(depth_map)
            all_normals.append(normal_map)
            all_valid_masks.append(valid_mask)

            self.logger.info(f"    Valid pixels: {np.sum(valid_mask)}")

        return all_depths, all_normals, all_valid_masks

    def _compute_frontmost_surfaces(
        self, all_depths: list, all_normals: list, all_valid_masks: list, proj_shape: tuple
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Determine which mask is frontmost at each pixel."""
        frontmost_mask = np.full(proj_shape, -1, dtype=int)
        frontmost_depth = np.full(proj_shape, np.inf)
        frontmost_normal = np.zeros((*proj_shape, 3))

        for mask_idx in range(len(self.mask_arrays)):
            valid = all_valid_masks[mask_idx]
            depths = all_depths[mask_idx]
            closer = valid & (depths < frontmost_depth)

            frontmost_mask[closer] = mask_idx
            frontmost_depth[closer] = depths[closer]
            frontmost_normal[closer] = all_normals[mask_idx][closer]

        return frontmost_mask, frontmost_depth, frontmost_normal

    def _render_final_image(
        self,
        frontmost_mask: np.ndarray,
        frontmost_depth: np.ndarray,
        frontmost_normal: np.ndarray,
        light_direction: np.ndarray,
        ambient: float,
        diffuse: float,
        mask_colors: list,
        background_color: Union[str, Tuple[float, float, float]],
    ) -> np.ndarray:
        """Render the final RGB image with lighting."""
        proj_shape = frontmost_mask.shape
        final_image_rgb = np.zeros((*proj_shape, 3))

        for mask_idx in range(len(self.mask_arrays)):
            is_frontmost = frontmost_mask == mask_idx

            if np.any(is_frontmost):
                image_rgb = self._compute_lighting(
                    frontmost_depth,
                    frontmost_normal,
                    is_frontmost,
                    light_direction,
                    ambient,
                    diffuse,
                    mask_colors[mask_idx],
                )
                final_image_rgb[is_frontmost] = image_rgb[is_frontmost]

        # Apply background
        bg_rgb = self._parse_background_color(background_color)
        final_valid_mask = frontmost_mask >= 0

        final_image = np.zeros((*proj_shape, 3))
        for i in range(3):
            final_image[:, :, i] = np.where(final_valid_mask, final_image_rgb[:, :, i], bg_rgb[i])

        return final_image

    def _create_figure(
        self,
        image: np.ndarray,
        direction: str,
        figsize: Optional[Tuple[float, float]],
        dpi: int,
        background_color: Union[str, Tuple[float, float, float]],
        bound_color: Tuple[float, float, float],
        bound_alpha: float,
        *,
        aspect_correct: bool,
        show_bounds: bool,
    ) -> plt.Figure:
        """Create the matplotlib figure."""
        aspect_ratio = self._get_aspect_ratio(direction)

        if figsize is None:
            base_size = 8
            figsize = (
                (base_size, base_size * aspect_ratio) if aspect_ratio > 1 else (base_size / aspect_ratio, base_size)
            )

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
        ax.imshow(image, origin="lower", aspect=aspect_ratio if aspect_correct else "auto")

        if show_bounds:
            self._draw_bounding_box(ax, direction, bound_color, bound_alpha)

        ax.axis("off")

        # Set background color
        bg_color = self._parse_background_color(background_color)
        bg_color_mpl = tuple(bg_color) if isinstance(bg_color, np.ndarray) else bg_color
        ax.set_facecolor(bg_color_mpl)
        fig.patch.set_facecolor(bg_color_mpl)

        plt.tight_layout(pad=0)
        plt.close()  # Close to prevent auto-display

        return fig

    def _draw_bounding_box(self, ax, direction: str, color: Tuple[float, float, float], alpha: float):
        """Draw a bounding box showing the image volume boundaries."""
        view_axes = {
            "anterior": (2, 0),
            "posterior": (2, 0),
            "right": (2, 1),
            "left": (2, 1),
            "superior": (1, 0),
            "inferior": (1, 0),
        }
        vert_axis, horiz_axis = view_axes[direction.lower()]
        height, width = self.shape[vert_axis], self.shape[horiz_axis]

        front_rect = plt.Rectangle((0, 0), width, height, fill=False, edgecolor=color, linewidth=2, alpha=alpha)
        ax.add_patch(front_rect)

        padding = 0.01
        ax.set_xlim(-width * padding, width * (1 + padding))
        ax.set_ylim(-height * padding, height * (1 + padding))

    def _ray_cast_single(self, mask_array: np.ndarray, direction: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Perform ray casting to generate depth map and surface normals."""
        config = self._get_view_config(direction)
        proj_shape = (self.shape[config["ax1"]], self.shape[config["ax2"]])

        depth_map = np.zeros(proj_shape, dtype=float)
        normal_map = np.zeros((*proj_shape, 3), dtype=float)
        valid_mask = np.zeros(proj_shape, dtype=bool)

        for i in range(proj_shape[0]):
            for j in range(proj_shape[1]):
                ray_line = self._extract_ray(mask_array, i, j, config)
                nonzero_indices = np.where(ray_line > 0)[0]

                if len(nonzero_indices) > 0:
                    depth_idx = nonzero_indices[0]
                    depth_map[i, j] = depth_idx
                    valid_mask[i, j] = True

                    actual_depth = depth_idx if config["forward"] else (self.shape[config["ray_axis"]] - 1 - depth_idx)
                    coords_3d = [0, 0, 0]
                    coords_3d[config["ax1"]] = i
                    coords_3d[config["ax2"]] = j
                    coords_3d[config["ray_axis"]] = actual_depth

                    normal_map[i, j] = self._estimate_normal(coords_3d, mask_array)

        return depth_map, normal_map, valid_mask

    def _extract_ray(self, mask_array: np.ndarray, i: int, j: int, config: dict) -> np.ndarray:
        """Extract a ray line from the mask array."""
        ray_axis = config["ray_axis"]
        forward = config["forward"]

        if ray_axis == 0:
            ray_line = mask_array[:, j, i]
        elif ray_axis == 1:
            ray_line = mask_array[j, :, i]
        else:  # ray_axis == 2
            ray_line = mask_array[j, i, :]

        return ray_line if forward else ray_line[::-1]

    def _estimate_normal(self, coords: list, mask_array: np.ndarray) -> np.ndarray:
        """Estimate surface normal at a point using finite differences."""
        x, y, z = coords
        gradient = np.zeros(3)

        for axis in range(3):
            c = [x, y, z]
            c_plus = c.copy()
            c_plus[axis] = min(self.shape[axis] - 1, c[axis] + 1)
            val_plus = mask_array[c_plus[0], c_plus[1], c_plus[2]]

            c_minus = c.copy()
            c_minus[axis] = max(0, c[axis] - 1)
            val_minus = mask_array[c_minus[0], c_minus[1], c_minus[2]]

            gradient[axis] = float(val_plus) - float(val_minus)

        norm = np.linalg.norm(gradient)
        return gradient / norm if norm > 1e-6 else np.array([0.0, 0.0, 1.0])

    def _compute_lighting(
        self,
        depth_map: np.ndarray,
        normal_map: np.ndarray,
        valid_mask: np.ndarray,
        light_direction: np.ndarray,
        ambient: float,
        diffuse: float,
        color: Tuple[float, float, float],
    ) -> np.ndarray:
        """Compute lighting and create RGB image."""
        h, w = depth_map.shape
        image = np.zeros((h, w, 3))

        # Normalize depth for depth-based shading
        depth_normalized = np.zeros_like(depth_map)
        if np.any(valid_mask):
            valid_depths = depth_map[valid_mask]
            if valid_depths.max() > valid_depths.min():
                depth_normalized[valid_mask] = (depth_map[valid_mask] - valid_depths.min()) / (
                    valid_depths.max() - valid_depths.min()
                )
            else:
                depth_normalized[valid_mask] = 0.5

        # Compute lighting
        for i in range(h):
            for j in range(w):
                if valid_mask[i, j]:
                    normal = normal_map[i, j]
                    diffuse_intensity = max(0, np.dot(normal, light_direction))
                    depth_factor = 1.0 - 0.4 * depth_normalized[i, j]
                    intensity = np.clip((ambient + diffuse * diffuse_intensity) * depth_factor, 0, 1)
                    image[i, j] = [c * intensity for c in color]

        return image
