"""Support for RYSE Smart Shades via BLE."""

import logging
from typing import Any

from ryseble.device import RyseBLEDevice
from ryseble.packets import build_get_position_packet, build_position_packet

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_ADDRESS, CONF_RX_UUID, CONF_TX_UUID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RYSE Smart Shade cover from a config entry."""
    device = RyseBLEDevice(
        entry.data[CONF_ADDRESS],
        entry.data[CONF_RX_UUID],
        entry.data[CONF_TX_UUID],
    )
    async_add_entities([SmartShadeCover(device)])


class SmartShadeCover(CoverEntity):
    """Representation of a RYSE Smart Shade BLE cover entity."""

    def __init__(self, device: RyseBLEDevice) -> None:
        """Initialize the Smart Shade cover entity."""
        self._device = device
        self._attr_name = f"Smart Shade {device.address}"
        self._attr_unique_id = f"smart_shade_{device.address}"
        self._state: str | None = None
        self._current_position: int | None = None
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
        if 0 <= position <= 100:
            self._current_position = 100 - position
            self._state = "open" if position < 100 else "closed"
            _LOGGER.debug("Updated cover position: %02X", position)
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shade."""
        pdata = build_position_packet(0x00)
        await self._device.write_data(pdata)
        _LOGGER.debug("Binary packet to change position to open")
        self._state = "open"

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shade."""
        pdata = build_position_packet(0x64)
        await self._device.write_data(pdata)
        _LOGGER.debug("Binary packet to change position to close")
        self._state = "closed"

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the shade to a specific position."""
        position = 100 - kwargs.get("position", 0)
        pdata = build_position_packet(position)
        await self._device.write_data(pdata)
        _LOGGER.debug("Binary packet to change position to a specific position")
        self._state = "open" if position < 100 else "closed"

    async def async_update(self) -> None:
        """Fetch the current state and position from the device."""
        if not self._device.client or not self._device.client.is_connected:
            paired = await self._device.pair()
            if not paired:
                _LOGGER.warning("Failed to pair with device, skipping update")
                return

        try:
            if self._current_position is None:
                bytesinfo = build_get_position_packet()
                await self._device.write_data(bytesinfo)
        except (TimeoutError, OSError) as err:
            _LOGGER.error("BLE communication error while reading device data: %s", err)
        except Exception:
            _LOGGER.exception("Unexpected error while reading device data")

    @property
    def is_closed(self) -> bool | None:
        """Return True if the shade is closed."""
        return self._state == "closed"

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        if self._current_position is None:
            return 50
        if not (0 <= self._current_position <= 100):
            _LOGGER.warning(
                "Invalid position value detected: %02X",
                self._current_position,
            )
            return 50
        return int(self._current_position)

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Return supported features for the cover entity."""
        return (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.SET_POSITION
        )
