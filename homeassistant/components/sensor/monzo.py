"""
Support for the Monzo API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.monzo/
"""
import logging

from homeassistant.components.monzo import (
    DATA_ACCOUNTID, DATA_BALANCE, DATA_MONZO_CLIENT, DATA_POTS,
    DEFAULT_ATTRIBUTION, DOMAIN, SENSORS, TOPIC_UPDATE, TYPE_BALANCE,
    TYPE_DAILY_SPEND, TYPE_POTS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.const import (ATTR_ID, ATTR_ATTRIBUTION)

DEPENDENCIES = ['monzo']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up a Monzo sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Monzo sensor based on a config entry."""
    monzo = hass.data[DOMAIN][DATA_MONZO_CLIENT][entry.entry_id]

    sensors = []
    for sensor_type in monzo.sensor_conditions:
        name, icon, unit = SENSORS[sensor_type]

        if sensor_type is TYPE_POTS:
            # Add a sensor for each pot with appropriate name
            pot_names = [pot['name'] for pot in monzo.data[DATA_POTS]]
            pot_ids = [pot['id'] for pot in monzo.data[DATA_POTS]]
            for name, pot_id in zip(pot_names, pot_ids):
                sensors.append(
                    MonzoSensor(
                        monzo, sensor_type, name, icon, unit, pot_id))
        else:
            account_id = monzo.data[DATA_ACCOUNTID]
            sensors.append(
                MonzoSensor(
                    monzo, sensor_type, name, icon, unit, account_id))

    async_add_entities(sensors, True)


class MonzoSensor(Entity):
    """Implementation of a Monzo sensor."""

    def __init__(self, monzo, sensor_type, name, icon, unit, account_id):
        """Initialize the Monzo sensor."""
        self.monzo = monzo
        self._dispatch_remove = None
        self._icon = icon
        self._name = name
        self._unique_account_id = account_id
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
                       ATTR_ID: account_id}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return 'monzo_{0}_{1}_{2}'.format(
            self._name, self._sensor_type, self._unique_account_id)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @callback
    def _update_data(self):
        """Update the state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._dispatch_remove = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, self._update_data)
        self.async_on_remove(self._dispatch_remove)

    async def async_update(self):
        """Update the state."""
        if self._sensor_type == TYPE_BALANCE:
            balance = self.monzo.data[DATA_BALANCE]
            self._state = balance['balance'] / 100
        elif self._sensor_type == TYPE_DAILY_SPEND:
            balance = self.monzo.data[DATA_BALANCE]
            self._state = balance['spend_today'] / 100
        elif self._sensor_type == TYPE_POTS:
            pots = self.monzo.data[DATA_POTS]
            pot = next(pot for pot in pots if
                       pot['id'] == self._unique_account_id)
            self._state = pot['balance'] / 100
