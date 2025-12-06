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
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RYSE Smart Shade cover from a config entry."""
    device = RyseBLEDevice(entry.unique_id)
    async_add_entities([RyseCoverEntity(device, entry)])


class RyseCoverEntity(CoverEntity):
    """Representation of a RYSE Smart Shade BLE cover entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, device: RyseBLEDevice, config_entry: ConfigEntry) -> None:
        """Initialize the Smart Shade cover entity."""
        self._device = device
        self._config_entry = config_entry

        self._attr_unique_id = f"{device.address}_cover"
        self._current_position: int | None = None
        self._attr_is_closed: bool | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=config_entry.title,
            manufacturer="RYSE",
            model="SmartShade BLE",
            connections={(CONNECTION_BLUETOOTH, self._device.address)},
        )

    # ------------------------------------------------------
    #   Home Assistant entity lifecycle
    # ------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""

        # Register the callback safely
        self._device.update_callback = self._update_position

        # Ensure cleanup automatically on removal
        self.async_on_remove(self._clear_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup before entity removal."""
        self._clear_callback()

    def _clear_callback(self) -> None:
        """Remove callback cleanly."""
        if getattr(self._device, "update_callback", None) == self._update_position:
            self._device.update_callback = None

    # ------------------------------------------------------
    #   Device callback
    # ------------------------------------------------------

    async def _update_position(self, position: int) -> None:
        """Update cover position when receiving notification."""
        if self._device.is_valid_position(position):
            self._current_position = self._device.get_real_position(position)
            self._attr_is_closed = self._device.is_closed(position)
            _LOGGER.debug("Updated cover position: %02X", position)

        self.async_write_ha_state()

    # ------------------------------------------------------
    #   Commands
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    #   State refresh
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    #   Properties
    # ------------------------------------------------------

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        if self._current_position is None:
            return None
        if not self._device.is_valid_position(self._current_position):
            _LOGGER.warning(
                "Invalid position value detected: %02X",
                self._current_position,
            )
            return None
        return self._current_position
