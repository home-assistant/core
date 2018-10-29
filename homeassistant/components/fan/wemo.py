"""
Support for WeMo humidifier.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan.wemo/
"""
import asyncio
import logging
from datetime import datetime, timedelta
import requests

import async_timeout

from homeassistant.components.fan import (
    DOMAIN, PLATFORM_SCHEMA, SUPPORT_SET_SPEED, FanEntity,
    SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import convert
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)
from homeassistant.const import ATTR_ENTITY_ID

DEPENDENCIES = ['wemo']
SCAN_INTERVAL = timedelta(seconds=10)
DATA_KEY = 'fan.wemo'

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_HUMIDITY = 'current_humidity'
ATTR_TARGET_HUMIDITY = 'target_humidity'
ATTR_FAN_MODE = 'fan_mode'
ATTR_FILTER_LIFE = 'filter_life'
ATTR_FILTER_EXPIRED = 'filter_expired'
ATTR_WATER_LEVEL = 'water_level'

SPEED_MINIMUM = 'minimum'
SPEED_MAXIMUM = 'maximum'

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

SUPPORTED_SPEEDS = [
    SPEED_OFF, SPEED_MINIMUM,
    SPEED_LOW, SPEED_MEDIUM,
    SPEED_HIGH, SPEED_MAXIMUM]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

WEMO_FAN_SPEED_TO_HASS = {
    WEMO_FAN_OFF: SPEED_OFF,
    WEMO_FAN_MINIMUM: SPEED_MINIMUM,
    WEMO_FAN_LOW: SPEED_LOW,
    WEMO_FAN_MEDIUM: SPEED_MEDIUM,
    WEMO_FAN_HIGH: SPEED_HIGH,
    WEMO_FAN_MAXIMUM: SPEED_MAXIMUM
}

HASS_FAN_SPEED_TO_WEMO = {
    SPEED_OFF: WEMO_FAN_OFF,
    SPEED_MINIMUM: WEMO_FAN_MINIMUM,
    SPEED_LOW: WEMO_FAN_LOW,
    SPEED_MEDIUM: WEMO_FAN_MEDIUM,
    SPEED_HIGH: WEMO_FAN_HIGH,
    SPEED_MAXIMUM: WEMO_FAN_MAXIMUM
}

SERVICE_SET_HUMIDITY = 'wemo_humidifier_set_humidity'

WEMO_HUMIDIFIER_SET_HUMIDITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_TARGET_HUMIDITY):
        vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
})


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up discovered WeMo humidifiers."""
    from pywemo import discovery

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']

        try:
            device = [WemoHumidifier(discovery.device_from_description(location, mac))
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as err:
            _LOGGER.error('Unable to access %s (%s)', location, err)
            raise PlatformNotReady

        if device:
            hass.data[DATA_KEY][device.entity_id] = device
            add_entities_callback(device))

    def service_handle(service):
        """Handle the WeMo humidifier services."""
        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_humidity = service.data.get(CONF_TARGET_HUMIDITY)

        if entity_id:
            humidifiers = [humidifier for device in hass.data[DATA_KEY].values() if
                       device.entity_id == entity_id]

        if humidifiers is None:
            _LOGGER.warning("Unable to find WeMo humidifier device %s",
                            str(entity_id))
            return

        if service.service == SERVICE_SET_HUMIDITY:
            for humidifier in humidifiers:
                humidifier.set_humidity(target_humidity)

    # Register dyson service(s)
    hass.services.register(
        DOMAIN, SERVICE_SET_HUMIDITY, service_handle,
        schema=WEMO_HUMIDIFIER_SET_HUMIDITY_SCHEMA)


class WemoHumidifier(FanEntity):
    """Representation of a WeMo humidifier."""

    def __init__(self, device):
        """Initialize the WeMo switch."""
        self.wemo = device
        self._state = None
        self._available = True
        self._update_lock = None

        self._fan_mode = None
        self._target_humidity = None
        self._current_humidity = None
        self._water_level = None
        self._filter_life = None
        self._filter_expired = None
        self._last_fan_on_mode = WEMO_FAN_MEDIUM

        # look up model name, name, and serial number once as it incurs network traffic
        self._model_name = self.wemo.model_name
        self._name = self.wemo.name
        self._serialnumber = self.wemo.serialnumber

    def _subscription_callback(self, _device, _type, _params):
        """Update the state by the Wemo device."""
        _LOGGER.info("Subscription update for %s", self.name)
        updated = self.wemo.subscription_update(_type, _params)
        self.hass.add_job(
            self._async_locked_subscription_callback(not updated))

    async def _async_locked_subscription_callback(self, force_update):
        """Handle an update from a subscription."""
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        await self._async_locked_update(force_update)
        self.async_schedule_update_ha_state()

    @property
    def should_poll(self):
        """Device should poll.

        Subscriptions push the state, however it won't detect if a device
        is no longer available. Use polling to detect if a device is available.
        """
        return True

    @property
    def unique_id(self):
        """Return the ID of this WeMo humidifier."""
        return self._serialnumber

    @property
    def name(self):
        """Return the name of the humidifier if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def available(self):
        """Return true if switch is available."""
        return self._available

    @property
    def icon(self):
        """Return the icon of device based on its type."""
        return 'mdi:water-percent'

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_CURRENT_HUMIDITY: self._current_humidity,
            ATTR_TARGET_HUMIDITY: self._target_humidity,
            ATTR_FAN_MODE: self._fan_mode,
            ATTR_WATER_LEVEL: self._water_level,
            ATTR_FILTER_LIFE: self._filter_life,
            ATTR_FILTER_EXPIRED: self._filter_expired
        }

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return WEMO_FAN_SPEED_TO_HASS.get(self._fan_mode)

    @property
    def speed_list(self: FanEntity) -> list:
        """Get the list of available speeds."""
        return SUPPORTED_SPEEDS

    @property
    def supported_features(self: FanEntity) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES

    async def async_added_to_hass(self):
        """Wemo humidifier added to HASS."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

        registry = self.hass.components.wemo.SUBSCRIPTION_REGISTRY
        await self.hass.async_add_job(registry.register, self.wemo)
        registry.on(self.wemo, None, self._subscription_callback)

    async def async_update(self):
        """Update WeMo state.

        Wemo has an aggressive retry logic that sometimes can take over a
        minute to return. If we don't get a state after 5 seconds, assume the
        Wemo humidifier is unreachable. If update goes through, it will be made
        available again.
        """
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        try:
            with async_timeout.timeout(5):
                await asyncio.shield(self._async_locked_update(True))
        except asyncio.TimeoutError:
            _LOGGER.warning('Lost connection to %s', self.name)
            self._available = False

    async def _async_locked_update(self, force_update):
        """Try updating within an async lock."""
        async with self._update_lock:
            await self.hass.async_add_job(self._update, force_update)

    def _update(self, force_update = True):
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
                _LOGGER.info('Reconnected to %s', self.name)
                self._available = True
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)
            self._available = False

    def turn_on(self: FanEntity, speed: str = None, **kwargs) -> None:
        """Turn the switch on."""
        if speed is None:
            self.wemo.set_state(self._last_fan_on_mode)
        else:
            self.set_speed(speed)

    def turn_off(self: FanEntity, **kwargs) -> None:
        """Turn the switch off."""
        self.wemo.set_state(WEMO_FAN_OFF)

    def set_speed(self: FanEntity, speed: str) -> None:
        """Set the fan_mode of the Humidifier."""
        self.wemo.set_state(HASS_FAN_SPEED_TO_WEMO.get(speed))

    def set_humidity(self: FanEntity, humidity: float) -> None:
        """Set the target humidity level for the Humidifier."""
        if humidity < 50:
            self.wemo.set_humidity(WEMO_HUMIDITY_45)
        elif humidity >= 50 and humidity < 55:
            self.wemo.set_humidity(WEMO_HUMIDITY_50)
        elif humidity >= 55 and humidity < 60:
            self.wemo.set_humidity(WEMO_HUMIDITY_55)
        elif humidity >= 60 and humidity < 100:
            self.wemo.set_humidity(WEMO_HUMIDITY_60)
        elif humidity >= 100:
            self.wemo.set_humidity(WEMO_HUMIDITY_100)
