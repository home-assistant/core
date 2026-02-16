"""Base entity for OpenDisplay."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

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

        hw_version = f"{manufacturer.board_type_name or f'UNKNOWN({manufacturer.board_type})'} rev. {manufacturer.board_revision}"

        color_scheme = getattr(
            display.color_scheme_enum, "name", f"UNKNOWN({display.color_scheme})"
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
            manufacturer=manufacturer.manufacturer_name or "OpenDisplay",
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
