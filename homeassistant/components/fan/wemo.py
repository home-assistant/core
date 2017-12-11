"""
Support for WeMo Humidifier.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan.wemo/
"""
import logging

from homeassistant.components.fan import (SPEED_OFF, SPEED_MINIMUM, SPEED_LOW,
                                          SPEED_MEDIUM, SPEED_HIGH,
                                          SPEED_MAXIMUM, FanEntity,
                                          SUPPORT_SET_SPEED,
                                          SUPPORT_TARGET_HUMIDITY,
                                          SUPPORT_FILTER_LIFE,
                                          SUPPORT_FILTER_EXPIRED,
                                          STATE_UNKNOWN)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)

WEMO_ON = 1
WEMO_OFF = 0

WEMO_HUMIDITY_45 = 0
WEMO_HUMIDITY_50 = 1
WEMO_HUMIDITY_55 = 2
WEMO_HUMIDITY_60 = 3
WEMO_HUMIDITY_100 = 4

WEMO_FAN_OFF = 0
WEMO_FAN_MINIMUM = 1
WEMO_FAN_LOW = 2
WEMO_FAN_MEDIUM = 3
WEMO_FAN_HIGH = 4
WEMO_FAN_MAXIMUM = 5

WEMO_WATER_EMPTY = 0
WEMO_WATER_LOW = 1
WEMO_WATER_GOOD = 2


# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up discovered WeMo humidifiers."""
    _LOGGER.debug('setup_platform called for wemo Humidifier device class')

    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
        device = discovery.device_from_description(location, mac)

        if device:
            add_devices_callback([WemoHumidifier(device)])
            _LOGGER.debug('Added a WeMo Humidifier device at: %s', location)


class WemoHumidifier(FanEntity):
    """Representation of a WeMo humidifier."""

    def __init__(self, device):
        """Initialize the WeMo humidifier."""
        self.wemo = device

        _LOGGER.debug('Init called for a WeMo humidifier device.')

        self._state = None
        self._fan_mode = None
        self._target_humidity = None
        self._current_humidity = None
        self._water_level = None
        self._filter_life = None
        self._filter_expired = None

        self._last_fan_on_mode = WEMO_FAN_MEDIUM

        # look up model name once as it incurs network traffic
        self._model_name = self.wemo.model_name

        wemo = get_component('wemo')
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.info("Subscription update for  %s", _device)
        updated = self.wemo.subscription_update(_type, _params)
        self._update(force_update=(not updated))

        if not hasattr(self, 'hass'):
            return
        self.schedule_update_ha_state()

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
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)

    def update(self):
        """Update WeMo state."""
        self._update(force_update=True)

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return False

    @property
    def unique_id(self):
        """Return the ID of this WeMo humidifier."""
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.wemo.name

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return 'mdi:water-percent'

    def turn_on(self: ToggleEntity, speed: str=None, **kwargs) -> None:
        """Turn the switch on."""
        self._state = WEMO_ON

        if speed is None:
            self.wemo.set_state(self._last_fan_on_mode)
        else:
            self.set_speed(speed)

        self.schedule_update_ha_state()

    def turn_off(self: ToggleEntity, **kwargs) -> None:
        """Turn the switch off."""
        self._state = WEMO_OFF
        self.wemo.set_state(WEMO_FAN_OFF)

        self.schedule_update_ha_state()

    def set_speed(self: ToggleEntity, speed: str) -> None:
        """Set the fan_mode of the Humidifier."""
        if speed == SPEED_OFF:
            self.wemo.set_state(WEMO_FAN_OFF)
            self._state = WEMO_OFF
        elif speed == SPEED_MINIMUM:
            self.wemo.set_state(WEMO_FAN_MINIMUM)
            self._state = WEMO_ON
        elif speed == SPEED_LOW:
            self.wemo.set_state(WEMO_FAN_LOW)
            self._state = WEMO_ON
        elif speed == SPEED_MEDIUM:
            self.wemo.set_state(WEMO_FAN_MEDIUM)
            self._state = WEMO_ON
        elif speed == SPEED_HIGH:
            self.wemo.set_state(WEMO_FAN_HIGH)
            self._state = WEMO_ON
        elif speed == SPEED_MAXIMUM:
            self.wemo.set_state(WEMO_FAN_MAXIMUM)
            self._state = WEMO_ON

        self.schedule_update_ha_state()

    def set_humidity(self: ToggleEntity, humidity: float) -> None:
        """Set the target humidity level for the Humidifier."""
        if humidity < 50:
            self.wemo.set_humidity(WEMO_HUMIDITY_45)
        elif ((humidity >= 50) and (humidity < 55)):
            self.wemo.set_humidity(WEMO_HUMIDITY_50)
        elif ((humidity >= 55) and (humidity < 60)):
            self.wemo.set_humidity(WEMO_HUMIDITY_55)
        elif ((humidity >= 60) and (humidity < 100)):
            self.wemo.set_humidity(WEMO_HUMIDITY_60)
        elif humidity >= 100:
            self.wemo.set_humidity(WEMO_HUMIDITY_100)

        self.schedule_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "current_humidity": self._current_humidity,
            "target_humidity": self._target_humidity,
            "fan_mode": self._fan_mode,
            "water_level": self._water_level,
            "filter_life": self._filter_life,
            "filter_expired": self._filter_expired
        }

    @property
    def speed(self) -> str:
        """Return the current speed."""
        current_wemo_speed = self.wemo.fan_mode
        if WEMO_FAN_OFF == current_wemo_speed:
            return SPEED_OFF
        elif WEMO_FAN_MINIMUM == current_wemo_speed:
            return SPEED_MINIMUM
        elif WEMO_FAN_LOW == current_wemo_speed:
            return SPEED_LOW
        elif WEMO_FAN_MEDIUM == current_wemo_speed:
            return SPEED_MEDIUM
        elif WEMO_FAN_HIGH == current_wemo_speed:
            return SPEED_HIGH
        elif WEMO_FAN_MAXIMUM == current_wemo_speed:
            return SPEED_MAXIMUM
        else:
            return STATE_UNKNOWN

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        supported_speeds = []
        supported_speeds.append(SPEED_OFF)
        supported_speeds.append(SPEED_MINIMUM)
        supported_speeds.append(SPEED_LOW)
        supported_speeds.append(SPEED_MEDIUM)
        supported_speeds.append(SPEED_HIGH)
        supported_speeds.append(SPEED_MAXIMUM)
        return supported_speeds

    @property
    def supported_features(self: ToggleEntity) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED | SUPPORT_TARGET_HUMIDITY |
                SUPPORT_FILTER_LIFE | SUPPORT_FILTER_EXPIRED
