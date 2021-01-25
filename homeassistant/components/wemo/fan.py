"""Support for WeMo humidifier."""
import asyncio
from datetime import timedelta
import logging

from pywemo.ouimeaux_device.api.service import ActionException
import voluptuous as vol

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

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
WEMO_FAN_LOW = 2  # Not used due to limitations of the base fan implementation
WEMO_FAN_MEDIUM = 3
WEMO_FAN_HIGH = 4  # Not used due to limitations of the base fan implementation
WEMO_FAN_MAXIMUM = 5

WEMO_WATER_EMPTY = 0
WEMO_WATER_LOW = 1
WEMO_WATER_GOOD = 2

SUPPORTED_SPEEDS = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

# Since the base fan object supports a set list of fan speeds,
# we have to reuse some of them when mapping to the 5 WeMo speeds
WEMO_FAN_SPEED_TO_HASS = {
    WEMO_FAN_OFF: SPEED_OFF,
    WEMO_FAN_MINIMUM: SPEED_LOW,
    WEMO_FAN_LOW: SPEED_LOW,  # Reusing SPEED_LOW
    WEMO_FAN_MEDIUM: SPEED_MEDIUM,
    WEMO_FAN_HIGH: SPEED_HIGH,  # Reusing SPEED_HIGH
    WEMO_FAN_MAXIMUM: SPEED_HIGH,
}

# Because we reused mappings in the previous dict, we have to filter them
# back out in this dict, or else we would have duplicate keys
HASS_FAN_SPEED_TO_WEMO = {
    v: k
    for (k, v) in WEMO_FAN_SPEED_TO_HASS.items()
    if k not in [WEMO_FAN_LOW, WEMO_FAN_HIGH]
}

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
        self._fan_mode = None
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
            ATTR_FAN_MODE: self._fan_mode,
            ATTR_WATER_LEVEL: self._water_level,
            ATTR_FILTER_LIFE: self._filter_life,
            ATTR_FILTER_EXPIRED: self._filter_expired,
        }

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return WEMO_FAN_SPEED_TO_HASS.get(self._fan_mode)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return SUPPORTED_SPEEDS

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES

    def _update(self, force_update=True):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)

            self._fan_mode = self.wemo.fan_mode_string
            self._target_humidity = self.wemo.desired_humidity_percent
            self._current_humidity = self.wemo.current_humidity_percent
            self._water_level = self.wemo.water_level_string
            self._filter_life = self.wemo.filter_life_percent
            self._filter_expired = self.wemo.filter_expired

            if self.wemo.fan_mode != WEMO_FAN_OFF:
                self._last_fan_on_mode = self.wemo.fan_mode

            if not self._available:
                _LOGGER.info("Reconnected to %s", self.name)
                self._available = True
        except (AttributeError, ActionException) as err:
            _LOGGER.warning("Could not update status for %s (%s)", self.name, err)
            self._available = False
            self.wemo.reconnect_with_device()

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn the switch on."""
        if speed is None:
            try:
                self.wemo.set_state(self._last_fan_on_mode)
            except ActionException as err:
                _LOGGER.warning("Error while turning on device %s (%s)", self.name, err)
                self._available = False
        else:
            self.set_speed(speed)

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        try:
            self.wemo.set_state(WEMO_FAN_OFF)
        except ActionException as err:
            _LOGGER.warning("Error while turning off device %s (%s)", self.name, err)
            self._available = False

        self.schedule_update_ha_state()

    def set_speed(self, speed: str) -> None:
        """Set the fan_mode of the Humidifier."""
        try:
            self.wemo.set_state(HASS_FAN_SPEED_TO_WEMO.get(speed))
        except ActionException as err:
            _LOGGER.warning(
                "Error while setting speed of device %s (%s)", self.name, err
            )
            self._available = False

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

        try:
            self.wemo.set_humidity(pywemo_humidity)
        except ActionException as err:
            _LOGGER.warning(
                "Error while setting humidity of device: %s (%s)", self.name, err
            )
            self._available = False

        self.schedule_update_ha_state()

    def reset_filter_life(self) -> None:
        """Reset the filter life to 100%."""
        try:
            self.wemo.reset_filter_life()
        except ActionException as err:
            _LOGGER.warning(
                "Error while resetting filter life on device: %s (%s)", self.name, err
            )
            self._available = False

        self.schedule_update_ha_state()
