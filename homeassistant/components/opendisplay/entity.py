"""Base entity and utilities for OpenDisplay."""

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
from typing import Any

from PIL import Image as PILImage, ImageOps

from homeassistant.components import bluetooth
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import ExtraStoredData

from . import OpenDisplayConfigEntry
from .const import DOMAIN


class OpenDisplayEntity(Entity):
    """Base class for OpenDisplay entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: OpenDisplayConfigEntry) -> None:
        """Initialize the entity."""
        address = entry.unique_id
        assert address is not None

        self._address = address
        self._entry_id = entry.entry_id
        self._attr_unique_id = address

        device_config = entry.runtime_data.device_config
        firmware = entry.runtime_data.firmware
        manufacturer = device_config.manufacturer
        display = device_config.displays[0]

        board_type = manufacturer.board_type_name or str(manufacturer.board_type)
        hw_version = f"{board_type} rev. {manufacturer.board_revision}"

        color_scheme = getattr(
            display.color_scheme_enum, "name", str(display.color_scheme)
        )

        size = (
            f'{display.screen_diagonal_inches:.1f}"'
            if display.screen_diagonal_inches is not None
            else f"{display.pixel_width}x{display.pixel_height}"
        )

        model = f"{size} {color_scheme}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=entry.title,
            manufacturer=manufacturer.manufacturer_name,
            model=model,
            hw_version=hw_version,
            sw_version=f"{firmware['major']}.{firmware['minor']}",
            configuration_url="https://opendisplay.org/firmware/config/",
            connections={(CONNECTION_BLUETOOTH, self._address)},
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return bluetooth.async_address_present(self.hass, self._address)


@dataclass
class OpenDisplayImageExtraStoredData(ExtraStoredData):
    """Extra stored data for OpenDisplay image entity."""

    image_last_updated: str | None
    has_stored_image: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation."""
        return {
            "image_last_updated": self.image_last_updated,
            "has_stored_image": self.has_stored_image,
        }

    @classmethod
    def from_dict(
        cls, restored: dict[str, Any]
    ) -> OpenDisplayImageExtraStoredData | None:
        """Initialize from a dict."""
        try:
            return cls(
                image_last_updated=restored["image_last_updated"],
                has_stored_image=restored["has_stored_image"],
            )
        except KeyError:
            return None


def load_image(path: str) -> PILImage.Image:
    """Load an image from disk and apply EXIF orientation."""
    image = PILImage.open(path)
    image.load()
    return ImageOps.exif_transpose(image)


def load_image_from_bytes(data: bytes) -> PILImage.Image:
    """Load an image from bytes and apply EXIF orientation."""
    image = PILImage.open(io.BytesIO(data))
    image.load()
    return ImageOps.exif_transpose(image)


def image_to_bytes(image: PILImage.Image) -> bytes:
    """Convert a PIL Image to PNG bytes."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def write_stored_image(path: Path, data: bytes) -> None:
    """Write image bytes to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_stored_image(path: Path) -> bytes | None:
    """Read stored image bytes from disk."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def delete_stored_image(path: Path) -> None:
    """Delete stored image from disk."""
    path.unlink(missing_ok=True)
