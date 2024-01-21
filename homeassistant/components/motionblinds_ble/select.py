"""Sensor entities for the MotionBlinds BLE integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    ATTR_SPEED,
    CONF_MAC_CODE,
    DOMAIN,
    ICON_SPEED,
    SETTING_MAX_MOTOR_FEEDBACK_TIME,
)
from .cover import GenericBlind, PositionCalibrationBlind
from .motionblinds_ble.const import MotionSpeedLevel

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


SELECT_TYPES: dict[str, SelectEntityDescription] = {
    ATTR_SPEED: SelectEntityDescription(
        key=ATTR_SPEED,
        translation_key=ATTR_SPEED,
        icon=ICON_SPEED,
        entity_category=EntityCategory.CONFIG,
        options=[str(speed_level.value) for speed_level in MotionSpeedLevel],
        has_entity_name=True,
    )
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up speed select entities based on a config entry."""

    blind: GenericBlind = hass.data[DOMAIN][entry.entry_id]

    if not isinstance(blind, PositionCalibrationBlind):
        async_add_entities([SpeedSelect(blind)])


class SpeedSelect(SelectEntity):
    """Representation of a speed select entity."""

    _has_selected_speed: bool = False
    _has_selected_speed_callback: Callable[[], None] | None = None

    def __init__(self, blind: GenericBlind) -> None:
        """Initialize the speed select entity."""
        _LOGGER.info(
            f"({blind.config_entry.data[CONF_MAC_CODE]}) Setting up speed select entity"
        )
        self.entity_description = SELECT_TYPES[ATTR_SPEED]
        self._blind = blind
        self._attr_unique_id: str = f"{blind.unique_id}_speed"
        self._attr_device_info = blind.device_info
        self._attr_current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        self._blind.async_register_speed_callback(self.async_update_speed)
        return await super().async_added_to_hass()

    @callback
    def async_update_speed(self, speed_level: MotionSpeedLevel | None) -> None:
        """Update the speed level."""
        if speed_level is None:
            # Disable callback when the connection has been closed
            self.async_disable_has_selected_speed_callback()
        if not self._has_selected_speed:
            self._attr_current_option = str(speed_level.value) if speed_level else None
        self.async_write_ha_state()

    def async_set_has_selected_speed(self, d: datetime):
        """Enable motor speed feedback again."""
        self._has_selected_speed = False

    def async_disable_has_selected_speed_callback(self):
        """Disable the has_selected_speed callback."""
        if callable(self._has_selected_speed_callback):
            self._has_selected_speed_callback()
            self._has_selected_speed_callback = None

    async def async_select_option(self, option: str) -> None:
        """Change the selected speed_level."""
        speed_level = MotionSpeedLevel(int(option))
        self.async_disable_has_selected_speed_callback()
        self._has_selected_speed = True
        await self._blind.async_speed(speed_level)
        # Ignore motor status feedback for a number of seconds
        async_call_later(
            hass=self.hass,
            delay=SETTING_MAX_MOTOR_FEEDBACK_TIME,
            action=self.async_set_has_selected_speed,
        )
        self._attr_current_option = str(speed_level.value) if speed_level else None
        self.async_write_ha_state()
