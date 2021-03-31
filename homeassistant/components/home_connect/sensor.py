"""Provides a sensor for Home Connect."""

from datetime import timedelta
import logging

from homeassistant.const import CONF_ENTITIES, DEVICE_CLASS_TIMESTAMP
import homeassistant.util.dt as dt_util

from .const import ATTR_VALUE, BSH_OPERATION_STATE, DOMAIN
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Home Connect sensor."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("sensor", [])
            entities += [HomeConnectSensor(**d) for d in entity_dicts]
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectSensor(HomeConnectEntity):
    """Sensor class for Home Connect."""

    def __init__(self, device, desc, key, unit, icon, device_class, sign=1):
        """Initialize the entity."""
        super().__init__(device, desc)
        self._state = None
        self._key = key
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._sign = sign

    @property
    def state(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def available(self):
        """Return true if the sensor is available."""
        return self._state is not None

    async def async_update(self):
        """Update the sensor's status."""
        status = self.device.appliance.status
        if self._key not in status:
            self._state = None
        else:
            if self.device_class == DEVICE_CLASS_TIMESTAMP:
                if ATTR_VALUE not in status[self._key]:
                    self._state = None
                elif (
                    self._state is not None
                    and self._sign == 1
                    and dt_util.parse_datetime(self._state) < dt_util.utcnow()
                ):
                    # if the date is supposed to be in the future but we're
                    # already past it, set state to None.
                    self._state = None
                else:
                    seconds = self._sign * float(status[self._key][ATTR_VALUE])
                    self._state = (
                        dt_util.utcnow() + timedelta(seconds=seconds)
                    ).isoformat()
            else:
                self._state = status[self._key].get(ATTR_VALUE)
                if self._key == BSH_OPERATION_STATE:
                    # Value comes back as an enum, we only really care about the
                    # last part, so split it off
                    # https://developer.home-connect.com/docs/status/operation_state
                    self._state = self._state.split(".")[-1]
        _LOGGER.debug("Updated, new state: %s", self._state)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class
