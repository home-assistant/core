"""Module for SIA Sensors."""

import datetime as dt
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT as SENSOR_FORMAT
from homeassistant.const import CONF_ZONE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.dt import utcnow

from .const import CONF_ACCOUNT, CONF_PING_INTERVAL, DATA_UPDATED, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up sia_sensor from a config entry."""
    devices = [
        device
        for hub in hass.data[DOMAIN].values()
        for device in hub.states.values()
        if isinstance(device, SIASensor)
    ]
    async_add_devices(devices)

    return True


class SIASensor(RestoreEntity):
    """Class for SIA Sensors."""

    def __init__(
        self, entity_id, name, device_class, zone, ping_interval, hass, account,
    ):
        """Create SIASensor object."""
        self._account = account
        self._should_poll = False
        self._device_class = device_class
        self.entity_id = SENSOR_FORMAT.format(entity_id)
        self._unique_id = entity_id
        self._state = utcnow()
        self._zone = zone
        self._ping_interval = str(ping_interval)
        self._attr = {
            CONF_ACCOUNT: self._account,
            CONF_PING_INTERVAL: self._ping_interval,
            CONF_ZONE: self._zone,
        }
        self._name = name
        self.hass = hass

    async def async_added_to_hass(self):
        """Once the sensor is added, see if it was there before and pull in that state."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state is not None:
            self.state = dt.datetime.strptime(state.state, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            return
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        """Schedule update."""
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Get unique_id."""
        return self._unique_id

    @property
    def state(self):
        """Return state."""
        return self._state.isoformat()

    @property
    def account(self):
        """Return device account."""
        return self._account

    @property
    def device_state_attributes(self):
        """Return attributes."""
        return self._attr

    def add_attribute(self, attr):
        """Update attributes."""
        self._attr.update(attr)

    @property
    def device_class(self):
        """Return device class."""
        return self._device_class

    @state.setter
    def state(self, state):
        """Set state."""
        self._state = state
        self.async_schedule_update_ha_state()

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:alarm-light-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._account)},
            "name": self._account,
            "via_device": (DOMAIN, self._account),
        }
