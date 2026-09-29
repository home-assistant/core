"""Support for RYSE Smart Shades via BLE."""

import logging
from typing import Any, override

from bleak import BleakError
from ryseble.device import RyseBLEDevice

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RyseConfigEntry, _async_unpair
from .const import MANUFACTURER_NAME

PARALLEL_UPDATES = 1  # one BLE connection at a time

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RyseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RYSE Smart Shade cover from a config entry."""
    device = entry.runtime_data
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

    def __init__(self, device: RyseBLEDevice, config_entry: RyseConfigEntry) -> None:
        """Initialize the Smart Shade cover entity."""
        self._device = device

        self._attr_unique_id = device.address
        self._current_position: int | None = None
        self._attr_is_closed: bool | None = None
        self._attr_available = True
        self._attr_device_info = DeviceInfo(
            manufacturer=MANUFACTURER_NAME,
            model="SmartShade BLE",
            connections={(CONNECTION_BLUETOOTH, self._device.address)},
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._device.update_callback = self._update_position
        self.async_on_remove(self._clear_callback)
        client = self._device.client
        if client and client.is_connected:
            try:
                await self._device.send_get_position()
            except (TimeoutError, OSError, EOFError, BleakError) as err:
                _LOGGER.debug("Could not request initial cover position: %s", err)

    def _clear_callback(self) -> None:
        """Restore the constructor default so ryseble will not await this entity.

        Assign ``None`` rather than deleting the attribute: the library object
        is constructed with ``update_callback = None``.
        """
        if self._device.update_callback == self._update_position:
            self._device.update_callback = None

    def _set_available(self, available: bool, reason: str | None = None) -> None:
        """Update availability, logging once on each transition."""
        if available == self._attr_available:
            return
        if available:
            _LOGGER.info("%s is available again", self.entity_id)
        else:
            _LOGGER.info("%s became unavailable: %s", self.entity_id, reason)
        self._attr_available = available

    def _clear_cached_position(self) -> None:
        """Drop cached cover state so a later poll will request a fresh position."""
        self._current_position = None
        self._attr_is_closed = None

    def _cached_position_is_valid(self) -> bool:
        """Return True when the cached Home Assistant position is still usable."""
        return self._current_position is not None and self._device.is_valid_position(
            self._current_position
        )

    async def _update_position(self, position: int) -> None:
        """Update cover position when receiving notification."""
        if self._device.is_valid_position(position):
            real_position = self._device.get_real_position(position)
            self._current_position = real_position
            self._attr_is_closed = self._device.is_closed(position)
            self._set_available(True)
            _LOGGER.debug(
                "Updated cover position: raw=%d mapped=%d", position, real_position
            )
        else:
            _LOGGER.warning("Invalid position value detected: %d", position)
            self._clear_cached_position()
        self.async_write_ha_state()

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shade."""
        try:
            await self._device.send_open()
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            raise HomeAssistantError(f"Failed to open cover: {err}") from err

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shade."""
        try:
            await self._device.send_close()
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            raise HomeAssistantError(f"Failed to close cover: {err}") from err

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the shade to a specific position."""
        ha_position = kwargs[ATTR_POSITION]
        device_position = self._device.get_real_position(ha_position)
        try:
            await self._device.send_set_position(device_position)
        except (TimeoutError, OSError, EOFError, BleakError) as err:
            raise HomeAssistantError(f"Failed to set cover position: {err}") from err

    async def async_update(self) -> None:
        """Fetch the current state and position from the device."""
        paired = False
        try:
            if not self._device.client or not self._device.client.is_connected:
                paired = await self._device.pair()
                if not paired:
                    await _async_unpair(self._device)
                    self._set_available(False, "failed to pair")
                    return

            if (
                self._current_position is not None
                and not self._cached_position_is_valid()
            ):
                self._clear_cached_position()

            if paired or self._current_position is None:
                await self._device.send_get_position()

            self._set_available(True)

        except (TimeoutError, OSError, EOFError, BleakError) as err:
            self._clear_cached_position()
            self._set_available(False, str(err))

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        return self._current_position
