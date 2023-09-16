"""Support for WeMo humidifier."""
from __future__ import annotations

from datetime import timedelta
import math
from typing import Any

from pywemo import DesiredHumidity, FanMode, Humidifier
import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import async_wemo_dispatcher_connect
from .const import SERVICE_RESET_FILTER_LIFE, SERVICE_SET_HUMIDITY
from .entity import WemoBinaryStateEntity
from .wemo_device import DeviceCoordinator

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0

ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_TARGET_HUMIDITY = "target_humidity"
ATTR_FAN_MODE = "fan_mode"
ATTR_FILTER_LIFE = "filter_life"
ATTR_FILTER_EXPIRED = "filter_expired"
ATTR_WATER_LEVEL = "water_level"

SPEED_RANGE = (FanMode.Minimum, FanMode.Maximum)  # off is not included

SET_HUMIDITY_SCHEMA = {
    vol.Required(ATTR_TARGET_HUMIDITY): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=100)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    _config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeMo binary sensors."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        async_add_entities([WemoHumidifier(coordinator)])

    await async_wemo_dispatcher_connect(hass, _discovered_wemo)

    platform = entity_platform.async_get_current_platform()

    # This will call WemoHumidifier.set_humidity(target_humidity=VALUE)
    platform.async_register_entity_service(
        SERVICE_SET_HUMIDITY, SET_HUMIDITY_SCHEMA, WemoHumidifier.set_humidity.__name__
    )

    # This will call WemoHumidifier.reset_filter_life()
    platform.async_register_entity_service(
        SERVICE_RESET_FILTER_LIFE, {}, WemoHumidifier.reset_filter_life.__name__
    )


class WemoHumidifier(WemoBinaryStateEntity, FanEntity):
    """Representation of a WeMo humidifier."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    wemo: Humidifier
    _last_fan_on_mode: FanMode

    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the WeMo switch."""
        super().__init__(coordinator)
        if self.wemo.fan_mode != FanMode.Off:
            self._last_fan_on_mode = self.wemo.fan_mode
        else:
            self._last_fan_on_mode = FanMode.High

    @property
    def icon(self) -> str:
        """Return the icon of device based on its type."""
        return "mdi:water-percent"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        return {
            ATTR_CURRENT_HUMIDITY: self.wemo.current_humidity_percent,
            ATTR_TARGET_HUMIDITY: self.wemo.desired_humidity_percent,
            ATTR_FAN_MODE: self.wemo.fan_mode_string,
            ATTR_WATER_LEVEL: self.wemo.water_level_string,
            ATTR_FILTER_LIFE: self.wemo.filter_life_percent,
            ATTR_FILTER_EXPIRED: self.wemo.filter_expired,
        }

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(SPEED_RANGE, self.wemo.fan_mode)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.wemo.fan_mode != FanMode.Off:
            self._last_fan_on_mode = self.wemo.fan_mode
        super()._handle_coordinator_update()

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        self._set_percentage(percentage)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        with self._wemo_call_wrapper("turn off"):
            self.wemo.set_state(FanMode.Off)

    def set_percentage(self, percentage: int) -> None:
        """Set the fan_mode of the Humidifier."""
        self._set_percentage(percentage)

    def _set_percentage(self, percentage: int | None) -> None:
        if percentage is None:
            named_speed = self._last_fan_on_mode
        elif percentage == 0:
            named_speed = FanMode.Off
        else:
            named_speed = FanMode(
                math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            )

        with self._wemo_call_wrapper("set speed"):
            self.wemo.set_state(named_speed)

    def set_humidity(self, target_humidity: float) -> None:
        """Set the target humidity level for the Humidifier."""
        if target_humidity < 50:
            pywemo_humidity = DesiredHumidity.FortyFivePercent
        elif 50 <= target_humidity < 55:
            pywemo_humidity = DesiredHumidity.FiftyPercent
        elif 55 <= target_humidity < 60:
            pywemo_humidity = DesiredHumidity.FiftyFivePercent
        elif 60 <= target_humidity < 100:
            pywemo_humidity = DesiredHumidity.SixtyPercent
        elif target_humidity >= 100:
            pywemo_humidity = DesiredHumidity.OneHundredPercent

        with self._wemo_call_wrapper("set humidity"):
            self.wemo.set_humidity(pywemo_humidity)

    def reset_filter_life(self) -> None:
        """Reset the filter life to 100%."""
        with self._wemo_call_wrapper("reset filter life"):
            self.wemo.reset_filter_life()
