"""Support for WeMo binary sensors."""
import asyncio
import logging

import async_timeout

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN as WEMO_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WeMo binary sensors."""

    async def _discovered_wemo(device):
        """Handle a discovered Wemo device."""
        async_add_entities([WemoBinarySensor(device)])

    async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.binary_sensor", _discovered_wemo)

    await asyncio.gather(
        *[
            _discovered_wemo(device)
            for device in hass.data[WEMO_DOMAIN]["pending"].pop("binary_sensor")
        ]
    )


class WemoBinarySensor(BinarySensorDevice):
    """Representation a WeMo binary sensor."""

    def __init__(self, device):
        """Initialize the WeMo sensor."""
        self.wemo = device
        self._state = None
        self._available = True
        self._update_lock = None
        self._model_name = self.wemo.model_name
        self._name = self.wemo.name
        self._serialnumber = self.wemo.serialnumber

    def _subscription_callback(self, _device, _type, _params):
        """Update the state by the Wemo sensor."""
        _LOGGER.debug("Subscription update for %s", self.name)
        updated = self.wemo.subscription_update(_type, _params)
        self.hass.add_job(self._async_locked_subscription_callback(not updated))

    async def _async_locked_subscription_callback(self, force_update):
        """Handle an update from a subscription."""
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        await self._async_locked_update(force_update)
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Wemo sensor added to Home Assistant."""
        # Define inside async context so we know our event loop
        self._update_lock = asyncio.Lock()

        registry = self.hass.data[WEMO_DOMAIN]["registry"]
        await self.hass.async_add_executor_job(registry.register, self.wemo)
        registry.on(self.wemo, None, self._subscription_callback)

    async def async_update(self):
        """Update WeMo state.

        Wemo has an aggressive retry logic that sometimes can take over a
        minute to return. If we don't get a state after 5 seconds, assume the
        Wemo sensor is unreachable. If update goes through, it will be made
        available again.
        """
        # If an update is in progress, we don't do anything
        if self._update_lock.locked():
            return

        try:
            with async_timeout.timeout(5):
                await asyncio.shield(self._async_locked_update(True))
        except asyncio.TimeoutError:
            _LOGGER.warning("Lost connection to %s", self.name)
            self._available = False

    async def _async_locked_update(self, force_update):
        """Try updating within an async lock."""
        async with self._update_lock:
            await self.hass.async_add_executor_job(self._update, force_update)

    def _update(self, force_update=True):
        """Update the sensor state."""
        try:
            self._state = self.wemo.get_state(force_update)

            if not self._available:
                _LOGGER.info("Reconnected to %s", self.name)
                self._available = True
        except AttributeError as err:
            _LOGGER.warning("Could not update status for %s (%s)", self.name, err)
            self._available = False

    @property
    def unique_id(self):
        """Return the id of this WeMo sensor."""
        return self._serialnumber

    @property
    def name(self):
        """Return the name of the service if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def available(self):
        """Return true if sensor is available."""
        return self._available

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.wemo.name,
            "identifiers": {(WEMO_DOMAIN, self.wemo.serialnumber)},
            "model": self.wemo.model_name,
            "manufacturer": "Belkin",
        }
