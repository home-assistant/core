"""Support for Speedtest.net internet speed testing sensor."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_BYTES_RECEIVED,
    ATTR_BYTES_SENT,
    ATTR_SERVER_COUNTRY,
    ATTR_SERVER_ID,
    ATTR_SERVER_NAME,
    ATTRIBUTION,
    DATA_UPDATED,
    DEFAULT_NAME,
    DOMAIN,
    ICON,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Set up the Speedtest.net sensor."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Transmission sensors."""

    client = hass.data[DOMAIN]

    dev = []
    for sensor_type in SENSOR_TYPES:
        dev.append(SpeedtestSensor(client, sensor_type))

    async_add_entities(dev, True)


class SpeedtestSensor(RestoreEntity):
    """Implementation of a speedtest.net sensor."""

    def __init__(self, client, sensor_type):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.speedtest_client = client
        self.type = sensor_type
        self._state = None
        self._data = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DEFAULT_NAME} {self._name}"

    @property
    def unique_id(self):
        """Return sensor unique_id."""
        return self.name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        if self._data is not None:
            if self.type == "download":
                attributes.update({ATTR_BYTES_RECEIVED: self._data["bytes_received"]})
            if self.type == "upload":
                attributes.update({ATTR_BYTES_SENT: self._data["bytes_sent"]})
            attributes.update(
                {
                    ATTR_SERVER_NAME: self._data["server"]["name"],
                    ATTR_SERVER_COUNTRY: self._data["server"]["country"],
                    ATTR_SERVER_ID: self._data["server"]["id"],
                }
            )
        return attributes

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state

        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    def update(self):
        """Get the latest data and update the states."""
        self._data = self.speedtest_client.data
        if self._data is None:
            return

        if self.type == "ping":
            self._state = self._data["ping"]
        elif self.type == "download":
            self._state = round(self._data["download"] / 10 ** 6, 2)
        elif self.type == "upload":
            self._state = round(self._data["upload"] / 10 ** 6, 2)

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
