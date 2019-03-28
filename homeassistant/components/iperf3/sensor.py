"""Support for Iperf3 sensors."""
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import ATTR_VERSION, DATA_UPDATED, DOMAIN as IPERF3_DOMAIN, SENSOR_TYPES

DEPENDENCIES = ['iperf3']

ATTRIBUTION = 'Data retrieved using Iperf3'

ICON = 'mdi:speedometer'

ATTR_PROTOCOL = 'Protocol'
ATTR_REMOTE_HOST = 'Remote Server'
ATTR_REMOTE_PORT = 'Remote Port'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info):
    """Set up the Iperf3 sensor."""
    sensors = []
    for iperf3_host in hass.data[IPERF3_DOMAIN].values():
        sensors.extend(
            [Iperf3Sensor(iperf3_host, sensor) for sensor in discovery_info]
        )
    async_add_entities(sensors, True)


class Iperf3Sensor(RestoreEntity):
    """A Iperf3 sensor implementation."""

    def __init__(self, iperf3_data, sensor_type):
        """Initialize the sensor."""
        self._name = \
            "{} {}".format(SENSOR_TYPES[sensor_type][0], iperf3_data.host)
        self._state = None
        self._sensor_type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._iperf3_data = iperf3_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_PROTOCOL: self._iperf3_data.protocol,
            ATTR_REMOTE_HOST: self._iperf3_data.host,
            ATTR_REMOTE_PORT: self._iperf3_data.port,
            ATTR_VERSION: self._iperf3_data.data[ATTR_VERSION]
        }

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

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
        data = self._iperf3_data.data.get(self._sensor_type)
        if data is not None:
            self._state = round(data, 2)

    @callback
    def _schedule_immediate_update(self, host):
        if host == self._iperf3_data.host:
            self.async_schedule_update_ha_state(True)
