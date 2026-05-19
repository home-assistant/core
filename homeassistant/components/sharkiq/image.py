# Shark IQ Floor Plan Image Entity.
# Renders a floor plan image from MARD polygon data
# Rooms as colored polygons with labels and no-go zones as red hatched areas.
# Support for doorways and lidar scan map

from __future__ import annotations

import asyncio
from collections.abc import Iterable
import math
from datetime import datetime
import io
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SHARK
from .coordinator import SharkIqConfigEntry, SharkIqUpdateCoordinator, SkegoxUpdateCoordinator, SharkDevice, get_device_model
from .sharkiq_pypi.sharkiq import Properties
from .skegox_device import SkegoxDevice

PADDING = 40
LABEL_FONT_SIZE = 14
NOGO_HATCH_ALPHA = 179
NOGO_HATCH_SPACING = 12
NOGO_HATCH_WIDTH = 2
IMAGE_MIN_DIM = 400
IMAGE_MAX_DIM = 1200

ROOM_COLOR = (66, 133, 244)

# Unsure what fonts are available
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:\\Windows\\Fonts\\arial.ttf",
]

# Compute min/max bounds from room polygons and no-go zones.
def _compute_bounds(room_polygons: dict[str, list[tuple[float, float]]], no_go_zones: list[dict[str, Any]],) -> tuple[float, float, float, float]:
    all_x = [x for points in room_polygons.values() for x, _ in points] + [x for zone in no_go_zones for x, _ in zone["points"]]
    all_y = [y for points in room_polygons.values() for _, y in points] + [y for zone in no_go_zones for _, y in zone["points"]]
    
    # Fallback bounds when no polygons or zones exist yet
    if not all_x:
        return 0, 0, 100, 100
    return min(all_x), min(all_y), max(all_x), max(all_y)

# Transform MARD coordinates to image pixel coordinates.
# MARD uses Cartesian (y-up), images use y-down, so we flip Y.
# X is also mirrored (``img_w - ...``) because MARD origin is top-right.
def _transform_point(x: float, y: float, min_x: float, min_y: float, max_x: float, max_y: float, img_w: int, img_h: int,) -> tuple[int, int]:
    data_w = max_x - min_x
    data_h = max_y - min_y
    if data_w == 0:
        data_w = 1
    if data_h == 0:
        data_h = 1

    scale_x = (img_w - 2 * PADDING) / data_w
    scale_y = (img_h - 2 * PADDING) / data_h
    scale = min(scale_x, scale_y)

    offset_x = PADDING + (img_w - 2 * PADDING - data_w * scale) / 2
    offset_y = PADDING + (img_h - 2 * PADDING - data_h * scale) / 2

    px = int(img_w - (offset_x + (x - min_x) * scale))
    py = int(img_h - (offset_y + (y - min_y) * scale))
    return px, py

# Transform polygon points to pixel coords and return them.
# Returns pixel coordinates without drawing so the caller can decide
# whether to fill, outline, or overlay the polygon separately.
def _draw_polygon(draw: Any, points: list[tuple[float, float]], min_x: float, min_y: float, max_x: float, max_y: float, img_w: int, img_h: int,) -> list[tuple[int, int]]:
    pixel_points = [_transform_point(x, y, min_x, min_y, max_x, max_y, img_w, img_h) for x, y in points]
    return pixel_points

# Create a hatch overlay image clipped to the polygon.
def _draw_hatch_overlay( pixel_points: list[tuple[int, int]], img_w: int, img_h: int, color: tuple[int, int, int, int],) -> Image.Image | None:

    if len(pixel_points) < 3:
        return None

    from PIL import Image, ImageDraw

    # Draw a binary mask of the polygon.
    xs = [p[0] for p in pixel_points]
    ys = [p[1] for p in pixel_points]
    min_px, max_px = min(xs), max(xs)
    min_py, max_py = min(ys), max(ys)

    mask_img = Image.new("L", (img_w, img_h), 0)
    mask_draw = ImageDraw.Draw(mask_img)
    mask_draw.polygon(pixel_points, fill=255)

    hatch_rgb = Image.new("RGB", (img_w, img_h), (0, 0, 0))
    hatch_draw = ImageDraw.Draw(hatch_rgb)

    # Draw diagonal hatch lines across the bounding box.
    diag_len = int(math.sqrt((max_px - min_px) ** 2 + (max_py - min_py) ** 2)) + NOGO_HATCH_SPACING
    for i in range(-diag_len, diag_len + NOGO_HATCH_SPACING, NOGO_HATCH_SPACING):
        x1 = min_px + i
        y1 = max_py
        x2 = min_px + i + (max_py - min_py)
        y2 = min_py

        x1 = max(0, min(img_w - 1, x1))
        y1 = max(0, min(img_h - 1, y1))
        x2 = max(0, min(img_w - 1, x2))
        y2 = max(0, min(img_h - 1, y2))

        hatch_draw.line([(x1, y1), (x2, y2)], fill=(color[0], color[1], color[2]), width=NOGO_HATCH_WIDTH)

    # Clip the hatch lines to the polygon mask.
    line_mask = hatch_rgb.split()[0].point(lambda p: 255 if p > 128 else 0)
    clipped_mask = Image.new("L", (img_w, img_h), 0)
    clipped_mask.paste(line_mask, mask=mask_img)

    if color[3] < 255:
        clipped_mask = clipped_mask.point(lambda p: int(p * color[3] / 255))

    # Apply the alpha channel from the input color.
    r, g, b = hatch_rgb.split()
    hatch = Image.merge("RGBA", (r, g, b, clipped_mask))
    
    # # Return an RGBA image ready for alpha compositing.
    return hatch

# Set up the Shark IQ floor plan image entities.
async def async_setup_entry(hass: HomeAssistant, config_entry: SharkIqConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,) -> None:
    coordinator = config_entry.runtime_data
    devices: Iterable[SharkDevice] = coordinator.shark_vacs.values()
    async_add_entities([SharkFloorPlanImage(d, coordinator) for d in devices if isinstance(d, SkegoxDevice)])


# Shark IQ floor plan image entity.
class SharkFloorPlanImage(CoordinatorEntity, ImageEntity):
    _coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator

    _attr_has_entity_name = True
    _attr_name = "Floor Plan"

    # Create a new SharkFloorPlanImage.
    def __init__(self, sharkiq: SharkDevice, coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator,) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass=coordinator.hass)
        self.sharkiq = sharkiq
        self._attr_unique_id = f"{sharkiq.serial_number}_floor_plan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
            manufacturer=SHARK,
            model=get_device_model(sharkiq),
            name=sharkiq.name,
            sw_version=sharkiq.get_property_value(Properties.ROBOT_FIRMWARE_VERSION),
        )
        self._attr_content_type = "image/jpeg"
        self._last_image: bytes | None = None
        self._attr_image_last_updated = None

    # Determine if the image entity is available.
    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.device_is_online(self.sharkiq.serial_number)
        )

    # Handle updated data from the coordinator.
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.last_update_success and self.coordinator.device_is_online(self.sharkiq.serial_number):
            tz = self._attr_image_last_updated.tzinfo if self._attr_image_last_updated else None
            self._attr_image_last_updated = datetime.now(tz)
        super()._handle_coordinator_update()

    # Render the floor plan map as a JPEG image.
    def _render_map(self) -> bytes | None:
        if not isinstance(self.sharkiq, SkegoxDevice):
            return None

        room_polygons = self.sharkiq.room_polygons
        no_go_zones = self.sharkiq.no_go_zones

        if not room_polygons and not no_go_zones:
            return None

        min_x, min_y, max_x, max_y = _compute_bounds(room_polygons, no_go_zones)

        data_w = max_x - min_x
        data_h = max_y - min_y
        if data_w == 0 or data_h == 0:
            return None

        aspect = data_w / data_h
        if aspect >= 1:
            img_w = min(IMAGE_MAX_DIM, max(IMAGE_MIN_DIM, int(data_w * 4)))
            img_h = int(img_w / aspect)
        else:
            img_h = min(IMAGE_MAX_DIM, max(IMAGE_MIN_DIM, int(data_h * 4)))
            img_w = int(img_h * aspect)

        img_w = max(img_w, IMAGE_MIN_DIM)
        img_h = max(img_h, IMAGE_MIN_DIM)

        from PIL import Image, ImageDraw, ImageFont

        image = Image.new("RGBA", (img_w, img_h), (245, 245, 245, 255))

        draw = ImageDraw.Draw(image, "RGBA")

        try:
            font = None
            for font_path in FONT_PATHS:
                try:
                    font = ImageFont.truetype(font_path, LABEL_FONT_SIZE)
                    break
                except (OSError, IOError):
                    continue
            # Fallback: default font if no system font was found
            if font is None:
                font = ImageFont.load_default()
        except Exception:
            # Second fallback for any unexpected font loading errors
            font = ImageFont.load_default()

        if self.sharkiq.floor_plan_edges or self.sharkiq.floor_plan_doors:
            self._draw_edges(draw, img_w, img_h, min_x, min_y, max_x, max_y)

        for room_name, points in room_polygons.items():
            pixel_points = _draw_polygon(draw, points, min_x, min_y, max_x, max_y, img_w, img_h)
            if len(pixel_points) < 3:
                continue

            draw.polygon(pixel_points, fill=None, outline=(*ROOM_COLOR, 200), width=2)

            xs = [p[0] for p in pixel_points]
            ys = [p[1] for p in pixel_points]
            cx = int(sum(xs) / len(xs))
            cy = int(sum(ys) / len(ys))

            text_bbox = draw.textbbox((0, 0), room_name, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            text_x = cx - text_w // 2
            text_y = cy - text_h // 2

            draw.text((text_x, text_y), room_name, fill=(*ROOM_COLOR, 255), font=font)

        for zone in no_go_zones:
            points = zone["points"]
            pixel_points = _draw_polygon(draw, points, min_x, min_y, max_x, max_y, img_w, img_h)
            if len(pixel_points) < 3:
                continue

            hatch_overlay = _draw_hatch_overlay(
                pixel_points,
                img_w,
                img_h,
                (220, 38, 38, NOGO_HATCH_ALPHA),
            )
            if hatch_overlay:
                image = Image.alpha_composite(image, hatch_overlay)
                draw = ImageDraw.Draw(image, "RGBA")

        image_rgb = image.convert("RGB")

        buf = io.BytesIO()
        image_rgb.save(buf, format="JPEG", quality=85)
        return buf.getvalue()

    # Draw floor plan edge and door lines scaled to room bounds.
    def _draw_edges(self, draw: Any, img_w: int, img_h: int, min_x: float, min_y: float, max_x: float, max_y: float,) -> None:
        edges = self.sharkiq.floor_plan_edges
        doors = self.sharkiq.floor_plan_doors
        if not edges and not doors:
            return

        # Compute edge/door bounds separately
        edge_all_x: list[float] = []
        edge_all_y: list[float] = []
        for (x1, y1), (x2, y2) in edges:
            edge_all_x.extend([x1, x2])
            edge_all_y.extend([y1, y2])
        for (x1, y1), (x2, y2) in doors:
            edge_all_x.extend([x1, x2])
            edge_all_y.extend([y1, y2])

        if not edge_all_x:
            return

        edge_min_x = min(edge_all_x)
        edge_min_y = min(edge_all_y)
        edge_max_x = max(edge_all_x)
        edge_max_y = max(edge_all_y)
        edge_w = edge_max_x - edge_min_x
        edge_h = edge_max_y - edge_min_y
        
        if edge_w == 0 or edge_h == 0:
            return

        room_w = max_x - min_x
        room_h = max_y - min_y

        if room_w == 0 or room_h == 0:
            return

        # Scale edges to fit room bounds (preserve aspect ratio)
        scale_edge_x = room_w / edge_w
        scale_edge_y = room_h / edge_h
        scale_edge = min(scale_edge_x, scale_edge_y)

        # Center edges within room bounds
        scaled_w = edge_w * scale_edge
        scaled_h = edge_h * scale_edge
        offset_x = min_x + (room_w - scaled_w) / 2 - edge_min_x * scale_edge
        offset_y = min_y + (room_h - scaled_h) / 2 - edge_min_y * scale_edge

        # Compute image pixel mapping
        data_w = max_x - min_x
        data_h = max_y - min_y
        scale_x = (img_w - 2 * PADDING) / data_w
        scale_y = (img_h - 2 * PADDING) / data_h
        scale = min(scale_x, scale_y)

        px_offset_x = PADDING + (img_w - 2 * PADDING - data_w * scale) / 2
        px_offset_y = PADDING + (img_h - 2 * PADDING - data_h * scale) / 2

        def to_pixel(x: float, y: float) -> tuple[int, int]:
            # Scale edge coords to room space, then to pixel coords
            room_x = x * scale_edge + offset_x
            room_y = y * scale_edge + offset_y
            # Edges use a different coordinate system than room polygons —
            # no X flip is needed because edge coords already match room orientation.
            px = int(px_offset_x + (room_x - min_x) * scale)
            py = int(img_h - (px_offset_y + (room_y - min_y) * scale))
            return px, py

        for (x1, y1), (x2, y2) in edges:
            p1 = to_pixel(x1, y1)
            p2 = to_pixel(x2, y2)
            draw.line([p1, p2], fill=(0, 0, 0, 255), width=2)

        # Door lines disabled — uncomment to restore
        # for (x1, y1), (x2, y2) in doors:
        #     p1 = to_pixel(x1, y1)
        #     p2 = to_pixel(x2, y2)
        #     draw.line([p1, p2], fill=(180, 180, 180, 255), width=2)

    # Return the floor plan image, preserving last good image on failure.
    async def async_image(self) -> bytes | None:
        rendered = await asyncio.to_thread(self._render_map)
        if rendered:
            self._last_image = rendered
        return self._last_image