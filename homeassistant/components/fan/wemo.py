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
    DOMAIN, PLATFORM_SCHEMA, SUPPORT_SET_SPEED, FanEntity)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.util import convert
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_STANDBY, STATE_UNKNOWN)

DEPENDENCIES = ['wemo']
SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

ATTR_SENSOR_STATE = 'sensor_state'
ATTR_SWITCH_MODE = 'switch_mode'
ATTR_CURRENT_STATE_DETAIL = 'state_detail'


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up discovered WeMo switches."""
    from pywemo import discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']

        try:
            device = discovery.device_from_description(location, mac)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as err:
            _LOGGER.error('Unable to access %s (%s)', location, err)
            raise PlatformNotReady

        if device:
            add_entities_callback([WemoHumidifier(device)])


class WemoHumidifier(FanEntity):
    """Representation of a WeMo humidifier."""

    def __init__(self, device):
        """Initialize the WeMo switch."""
        self.wemo = device
        self._state = None
        self._available = True
        self._update_lock = None
        # look up model name once as it incurs network traffic
        self._model_name = self.wemo.model_name

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
        return self.wemo.serialnumber

    @property
    def name(self):
        """Return the name of the humidifier if any."""
        return self.wemo.name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        return attr

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self._state

    @property
    def available(self):
        """Return true if switch is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the humidifier on."""
        self.wemo.on()

    def turn_off(self, **kwargs):
        """Turn the humidifier off."""
        self.wemo.off()

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

    def _update(self, force_update):
        """Update the device state."""
        try:
            self._state = self.wemo.get_state(force_update)

            if not self._available:
                _LOGGER.info('Reconnected to %s', self.name)
                self._available = True
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)",
                            self.name, err)
            self._available = False
