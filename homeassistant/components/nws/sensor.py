"""Provides alert sensor from NWS."""
from datetime import timedelta
import logging

from homeassistant.const import ATTR_ATTRIBUTION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utcnow

from . import base_unique_id
from .const import (
    ATTR_ALERTS,
    ATTR_ZONES,
    ATTRIBUTION,
    COORDINATOR_ALERTS,
    DOMAIN,
    EVENT_ALERTS,
    NWS_DATA,
)

_LOGGER = logging.getLogger(__name__)

ALERT_VALID_TIME = timedelta(minutes=10)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the NWS sensors."""

    hass_data = hass.data[DOMAIN][config_entry.entry_id]
    nws = hass_data[NWS_DATA]
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    coordinator = hass_data[COORDINATOR_ALERTS]

    await coordinator.async_refresh()
    if not nws.all_zones:
        raise PlatformNotReady

    async_add_entities(
        [
            NWSAlertSensor(
                f"{base_unique_id(latitude, longitude)}_alerts", coordinator, nws,
            ),
        ],
        False,
    )


class NWSAlertSensor(Entity):
    """Representation of a sensor entity for NWS alert values."""

    def __init__(self, unique_id, coordinator, nws):
        """Initialize the sensor."""
        self._unique_id = unique_id
        self._coordinator = coordinator
        self._nws = nws

        self._zones = sorted(nws.all_zones)
        self._name = f"{' '.join(self._zones)} Alerts"

    @property
    def unique_id(self):
        """Sensor Unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:weather-cloudy-alert"

    @property
    def state(self):
        """Return entity state as number of alerts."""
        return len(self._alerts)

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        if self._coordinator.last_update_success_time:
            last_success_time = (
                utcnow() - self._coordinator.last_update_success_time < ALERT_VALID_TIME
            )
        else:
            last_success_time = False
        return self._coordinator.last_update_success or last_success_time

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement."""
        return "alerts"

    @property
    def device_state_attributes(self):
        """Return the sensor attributes."""
        return {
            ATTR_ALERTS: self._alerts,
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_ZONES: self._zones,
        }

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    @callback
    def _update_state(self):
        if self._coordinator.data:
            self.hass.bus.fire(
                EVENT_ALERTS,
                {ATTR_ALERTS: self._coordinator.data, ATTR_ZONES: self._zones},
            )
        self._alerts = self._nws.alerts_all_zones
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self._update_state))
        self._update_state()
