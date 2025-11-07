"""Support for RYSE Smart Shades via BLE."""

import logging
from typing import Any

from ryseble.device import RyseBLEDevice

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RYSE Smart Shade cover from a config entry."""
    device = RyseBLEDevice(entry.unique_id)
    async_add_entities([RyseCoverEntity(device)])


class RyseCoverEntity(CoverEntity):
    """Representation of a RYSE Smart Shade BLE cover entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: RyseBLEDevice) -> None:
        """Initialize the Smart Shade cover entity."""
        self._device = device
        self._attr_unique_id = f"{device.address}_cover"
        self._current_position: int | None = None
        self._attr_is_closed: bool | None = None
        self._device.update_callback = self._update_position

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information for Home Assistant device registry."""
        return DeviceInfo(
            identifiers={("ryse", self._device.address)},
            name=f"Smart Shade {self._device.address}",
            manufacturer="RYSE",
            model="SmartShade BLE",
            connections={("bluetooth", self._device.address)},
        )

    async def _update_position(self, position: int) -> None:
        """Update cover position when receiving notification."""
        if self._device.is_valid_position(position):
            self._current_position = self._device.get_real_position(position)
            self._attr_is_closed = self._device.is_closed(position)
            _LOGGER.debug("Updated cover position: %02X", position)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shade."""
        await self._device.send_open()
        _LOGGER.debug("Change position to open")
        self._attr_is_closed = False

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shade."""
        await self._device.send_close()
        _LOGGER.debug("Change position to close")
        self._attr_is_closed = True

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the shade to a specific position."""
        position = self._device.get_real_position(kwargs.get(ATTR_POSITION, 0))
        await self._device.send_set_position(position)
        _LOGGER.debug("Change position to a specific position")
        self._attr_is_closed = self._device.is_closed(position)

    async def async_update(self) -> None:
        """Fetch the current state and position from the device."""
        if not self._device.client or not self._device.client.is_connected:
            paired = await self._device.pair()
            if not paired:
                if self._attr_available:
                    _LOGGER.debug("Failed to pair with device, skipping update")
                self._attr_available = False
                return
        else:
            self._attr_available = True

        try:
            if self._current_position is None:
                await self._device.send_get_position()
        except (TimeoutError, OSError) as err:
            _LOGGER.error("BLE communication error while reading device data: %s", err)
        except Exception:
            _LOGGER.exception("Unexpected error while reading device data")

    @property
    def is_closed(self) -> bool | None:
        """Return True if the shade is closed."""
        return self._attr_is_closed

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        if self._current_position is None:
            return None
        if not (self._device.is_valid_position(self._current_position)):
            _LOGGER.warning(
                "Invalid position value detected: %02X",
                self._current_position,
            )
            return None
        return int(self._current_position)

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )
