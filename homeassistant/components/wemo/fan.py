"""Support for WeMo humidifier."""
import asyncio
from datetime import timedelta
import logging
import math

import voluptuous as vol

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    DOMAIN as WEMO_DOMAIN,
    SERVICE_RESET_FILTER_LIFE,
    SERVICE_SET_HUMIDITY,
)
from .entity import WemoSubscriptionEntity

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_TARGET_HUMIDITY = "target_humidity"
ATTR_FAN_MODE = "fan_mode"
ATTR_FILTER_LIFE = "filter_life"
ATTR_FILTER_EXPIRED = "filter_expired"
ATTR_WATER_LEVEL = "water_level"

# The WEMO_ constants below come from pywemo itself
WEMO_ON = 1
WEMO_OFF = 0

WEMO_HUMIDITY_45 = 0
WEMO_HUMIDITY_50 = 1
WEMO_HUMIDITY_55 = 2
WEMO_HUMIDITY_60 = 3
WEMO_HUMIDITY_100 = 4

WEMO_FAN_OFF = 0
WEMO_FAN_MINIMUM = 1
WEMO_FAN_MEDIUM = 4
WEMO_FAN_MAXIMUM = 5

SPEED_RANGE = (WEMO_FAN_MINIMUM, WEMO_FAN_MAXIMUM)  # off is not included

WEMO_WATER_EMPTY = 0
WEMO_WATER_LOW = 1
WEMO_WATER_GOOD = 2

SUPPORTED_FEATURES = SUPPORT_SET_SPEED


SET_HUMIDITY_SCHEMA = {
    vol.Required(ATTR_TARGET_HUMIDITY): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=100)
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo binary sensors."""

    async def _discovered_wemo(device):
        """Handle a discovered Wemo device."""
        async_add_entities([WemoHumidifier(device)])

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.fan", _discovered_wemo)

    await asyncio.gather(
        *[
            _discovered_wemo(device)
            for device in hass.data[WEMO_DOMAIN]["pending"].pop("fan")
        ]
    )

    platform = entity_platform.current_platform.get()

    # This will call WemoHumidifier.set_humidity(target_humidity=VALUE)
    platform.async_register_entity_service(
        SERVICE_SET_HUMIDITY, SET_HUMIDITY_SCHEMA, WemoHumidifier.set_humidity.__name__
    )

    # This will call WemoHumidifier.reset_filter_life()
    platform.async_register_entity_service(
        SERVICE_RESET_FILTER_LIFE, {}, WemoHumidifier.reset_filter_life.__name__
    )


class WemoHumidifier(WemoSubscriptionEntity, FanEntity):
    """Representation of a WeMo humidifier."""

    def __init__(self, device):
        """Initialize the WeMo switch."""
        super().__init__(device)
        self._fan_mode = WEMO_FAN_OFF
        self._fan_mode_string = None
        self._target_humidity = None
        self._current_humidity = None
        self._water_level = None
        self._filter_life = None
        self._filter_expired = None
        self._last_fan_on_mode = WEMO_FAN_MEDIUM

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return "mdi:water-percent"

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_CURRENT_HUMIDITY: self._current_humidity,
            ATTR_TARGET_HUMIDITY: self._target_humidity,
            ATTR_FAN_MODE: self._fan_mode_string,
            ATTR_WATER_LEVEL: self._water_level,
            ATTR_FILTER_LIFE: self._filter_life,
            ATTR_FILTER_EXPIRED: self._filter_expired,
        }

    @property
    def percentage(self) -> str:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(SPEED_RANGE, self._fan_mode)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES

    def _update(self, force_update=True):
        """Update the device state."""
        with self._wemo_exception_handler("update status"):
            self._state = self.wemo.get_state(force_update)

            self._fan_mode = self.wemo.fan_mode
            self._fan_mode_string = self.wemo.fan_mode_string
            self._target_humidity = self.wemo.desired_humidity_percent
            self._current_humidity = self.wemo.current_humidity_percent
            self._water_level = self.wemo.water_level_string
            self._filter_life = self.wemo.filter_life_percent
            self._filter_expired = self.wemo.filter_expired

            if self.wemo.fan_mode != WEMO_FAN_OFF:
                self._last_fan_on_mode = self.wemo.fan_mode

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn the fan on."""
        self.set_percentage(percentage)

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        with self._wemo_exception_handler("turn off"):
            self.wemo.set_state(WEMO_FAN_OFF)

        self.schedule_update_ha_state()

    def set_percentage(self, percentage: int) -> None:
        """Set the fan_mode of the Humidifier."""
        if percentage is None:
            named_speed = self._last_fan_on_mode
        elif percentage == 0:
            named_speed = WEMO_FAN_OFF
        else:
            named_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        with self._wemo_exception_handler("set speed"):
            self.wemo.set_state(named_speed)

        self.schedule_update_ha_state()

    def set_humidity(self, target_humidity: float) -> None:
        """Set the target humidity level for the Humidifier."""
        if target_humidity < 50:
            pywemo_humidity = WEMO_HUMIDITY_45
        elif 50 <= target_humidity < 55:
            pywemo_humidity = WEMO_HUMIDITY_50
        elif 55 <= target_humidity < 60:
            pywemo_humidity = WEMO_HUMIDITY_55
        elif 60 <= target_humidity < 100:
            pywemo_humidity = WEMO_HUMIDITY_60
        elif target_humidity >= 100:
            pywemo_humidity = WEMO_HUMIDITY_100

        with self._wemo_exception_handler("set humidity"):
            self.wemo.set_humidity(pywemo_humidity)

        self.schedule_update_ha_state()

    def reset_filter_life(self) -> None:
        """Reset the filter life to 100%."""
        with self._wemo_exception_handler("reset filter life"):
            self.wemo.reset_filter_life()

        self.schedule_update_ha_state()
