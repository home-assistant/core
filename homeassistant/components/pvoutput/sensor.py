"""Support for getting collected information from PVOutput."""
from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timedelta
import logging
from typing import cast

import voluptuous as vol

from homeassistant.components.rest.data import RestData
from homeassistant.components.sensor import (
    ATTR_NATIVE_VALUE,
    DEVICE_CLASS_ENERGY,
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_DATE,
    ATTR_TEMPERATURE,
    ATTR_TIME,
    ATTR_VOLTAGE,
    CONF_API_KEY,
    CONF_NAME,
    ENERGY_WATT_HOUR,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)
_ENDPOINT = "http://pvoutput.org/service/r2/getstatus.jsp"

ATTR_ENERGY_GENERATION = "energy_generation"
ATTR_POWER_GENERATION = "power_generation"
ATTR_ENERGY_CONSUMPTION = "energy_consumption"
ATTR_POWER_CONSUMPTION = "power_consumption"
ATTR_EFFICIENCY = "efficiency"

CONF_SYSTEM_ID = "system_id"

DEFAULT_NAME = "PVOutput"
DEFAULT_VERIFY_SSL = True

SCAN_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SYSTEM_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the PVOutput sensor."""
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    system_id = config.get(CONF_SYSTEM_ID)
    method = "GET"
    payload = auth = None
    verify_ssl = DEFAULT_VERIFY_SSL
    headers = {"X-Pvoutput-Apikey": api_key, "X-Pvoutput-SystemId": system_id}

    rest = RestData(hass, method, _ENDPOINT, auth, headers, None, payload, verify_ssl)
    await rest.async_update()

    if rest.data is None:
        _LOGGER.error("Unable to fetch data from PVOutput")
        return False

    async_add_entities([PvoutputSensor(rest, name)])


class PvoutputSensor(SensorEntity, RestoreEntity):
    """Representation of a PVOutput sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_native_unit_of_measurement = ENERGY_WATT_HOUR

    _old_state: int | None = None

    def __init__(self, rest, name):
        """Initialize a PVOutput sensor."""
        self.rest = rest
        self._attr_name = name
        self.pvcoutput = None
        self.status = namedtuple(
            "status",
            [
                ATTR_DATE,
                ATTR_TIME,
                ATTR_ENERGY_GENERATION,
                ATTR_POWER_GENERATION,
                ATTR_ENERGY_CONSUMPTION,
                ATTR_POWER_CONSUMPTION,
                ATTR_EFFICIENCY,
                ATTR_TEMPERATURE,
                ATTR_VOLTAGE,
            ],
        )

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.pvcoutput is not None:
            return self.pvcoutput.energy_generation
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        if self.pvcoutput is not None:
            return {
                ATTR_ENERGY_GENERATION: self.pvcoutput.energy_generation,
                ATTR_POWER_GENERATION: self.pvcoutput.power_generation,
                ATTR_ENERGY_CONSUMPTION: self.pvcoutput.energy_consumption,
                ATTR_POWER_CONSUMPTION: self.pvcoutput.power_consumption,
                ATTR_EFFICIENCY: self.pvcoutput.efficiency,
                ATTR_TEMPERATURE: self.pvcoutput.temperature,
                ATTR_VOLTAGE: self.pvcoutput.voltage,
            }

    async def async_update(self):
        """Get the latest data from the PVOutput API and updates the state."""
        await self.rest.async_update()
        self._async_update_from_rest_data()

        new_state: int | None = None
        state = cast("str | None", self.state)
        if state is not None:
            new_state = int(state)

        did_reset = False
        if new_state is None:
            did_reset = False
        elif self._old_state is None:
            did_reset = True
        elif new_state == 0:
            did_reset = self._old_state != 0
        elif new_state < self._old_state:
            did_reset = True

        if did_reset:
            self._attr_last_reset = dt_util.utcnow()

        if new_state is not None:
            self._old_state = new_state

    async def async_added_to_hass(self):
        """Ensure the data from the initial update is reflected in the state."""
        last_state = await self.async_get_last_state()
        if last_state is not None:
            if "last_reset" in last_state.attributes:
                self._attr_last_reset = dt_util.as_utc(
                    datetime.fromisoformat(last_state.attributes["last_reset"])
                )
            self._old_state = int(last_state.attributes.get(ATTR_NATIVE_VALUE))

        self._async_update_from_rest_data()

    @callback
    def _async_update_from_rest_data(self):
        """Update state from the rest data."""
        try:
            # https://pvoutput.org/help/api_specification.html#get-status-service
            self.pvcoutput = self.status._make(self.rest.data.split(","))
        except TypeError:
            self.pvcoutput = None
            _LOGGER.error("Unable to fetch data from PVOutput. %s", self.rest.data)
