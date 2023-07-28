"""Support for SwitchBot curtains."""
from __future__ import annotations

import logging
from typing import Any

import switchbot

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

# Initialize the logger
_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot curtain based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    if isinstance(coordinator.device, switchbot.SwitchbotBlindTilt):
        async_add_entities([SwitchBotBlindTiltEntity(coordinator)])
    else:
        async_add_entities([SwitchBotCurtainEntity(coordinator)])


class SwitchBotCurtainEntity(SwitchbotEntity, CoverEntity, RestoreEntity):
    """Representation of a Switchbot."""

    _device: switchbot.SwitchbotCurtain
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )
    _attr_translation_key = "cover"
    _attr_name = None

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state or ATTR_CURRENT_POSITION not in last_state.attributes:
            return

        self._attr_current_cover_position = last_state.attributes.get(
            ATTR_CURRENT_POSITION
        )
        self._last_run_success = last_state.attributes.get("last_run_success")
        if self._attr_current_cover_position is not None:
            self._attr_is_closed = self._attr_current_cover_position <= 20

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the curtain."""

        _LOGGER.debug("Switchbot to open curtain %s", self._address)
        self._last_run_success = bool(await self._device.open())
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the curtain."""

        _LOGGER.debug("Switchbot to close the curtain %s", self._address)
        self._last_run_success = bool(await self._device.close())
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the moving of this device."""

        _LOGGER.debug("Switchbot to stop %s", self._address)
        self._last_run_success = bool(await self._device.stop())
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover shutter to a specific position."""
        position = kwargs.get(ATTR_POSITION)

        _LOGGER.debug("Switchbot to move at %d %s", position, self._address)
        self._last_run_success = bool(await self._device.set_position(position))
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_cover_position = self.parsed_data["position"]
        self._attr_is_closed = self.parsed_data["position"] <= 20
        self._attr_is_opening = self.parsed_data["inMotion"]
        self.async_write_ha_state()


class SwitchBotBlindTiltEntity(SwitchbotEntity, CoverEntity, RestoreEntity):
    """Representation of a Switchbot."""

    _device: switchbot.SwitchbotBlindTilt
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )
    _attr_name = None
    _attr_translation_key = "cover"
    CLOSED_UP_THRESHOLD = 80
    CLOSED_DOWN_THRESHOLD = 20

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state or ATTR_CURRENT_TILT_POSITION not in last_state.attributes:
            return

        self._attr_current_cover_tilt_position = last_state.attributes.get(
            ATTR_CURRENT_TILT_POSITION
        )
        self._last_run_success = last_state.attributes.get("last_run_success")
        if (_tilt := self._attr_current_cover_position) is not None:
            self._attr_is_closed = (_tilt < self.CLOSED_DOWN_THRESHOLD) or (
                _tilt > self.CLOSED_UP_THRESHOLD
            )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the tilt."""

        _LOGGER.debug("Switchbot to open blind tilt %s", self._address)
        self._last_run_success = bool(await self._device.open())
        self.async_write_ha_state()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the tilt."""

        _LOGGER.debug("Switchbot to close the blind tilt %s", self._address)
        self._last_run_success = bool(await self._device.close())
        self.async_write_ha_state()

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the moving of this device."""

        _LOGGER.debug("Switchbot to stop %s", self._address)
        self._last_run_success = bool(await self._device.stop())
        self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        position = kwargs.get(ATTR_TILT_POSITION)

        _LOGGER.debug("Switchbot to move at %d %s", position, self._address)
        self._last_run_success = bool(await self._device.set_position(position))
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _tilt = self.parsed_data["tilt"]
        self._attr_current_cover_tilt_position = _tilt
        self._attr_is_closed = (_tilt < self.CLOSED_DOWN_THRESHOLD) or (
            _tilt > self.CLOSED_UP_THRESHOLD
        )
        self._attr_is_opening = self.parsed_data["motionDirection"]["opening"]
        self._attr_is_closing = self.parsed_data["motionDirection"]["closing"]
        self.async_write_ha_state()
