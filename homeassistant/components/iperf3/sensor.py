"""Support for Iperf3 sensors."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from . import ATTR_VERSION, DATA_UPDATED, DOMAIN as IPERF3_DOMAIN, SENSOR_TYPES

ATTRIBUTION = "Data retrieved using Iperf3"

ICON = "mdi:speedometer"

ATTR_PROTOCOL = "Protocol"
ATTR_REMOTE_HOST = "Remote Server"
ATTR_REMOTE_PORT = "Remote Port"


async def async_setup_platform(hass, config, async_add_entities, discovery_info):
    """Set up the Iperf3 sensor."""
    entities = [
        Iperf3Sensor(iperf3_host, description)
        for iperf3_host in hass.data[IPERF3_DOMAIN].values()
        for description in SENSOR_TYPES
        if description.key in discovery_info
    ]
    async_add_entities(entities, True)


class Iperf3Sensor(RestoreEntity, SensorEntity):
    """A Iperf3 sensor implementation."""

    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(self, iperf3_data, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._iperf3_data = iperf3_data
        self._attr_name = f"{description.name} {iperf3_data.host}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_PROTOCOL: self._iperf3_data.protocol,
            ATTR_REMOTE_HOST: self._iperf3_data.host,
            ATTR_REMOTE_PORT: self._iperf3_data.port,
            ATTR_VERSION: self._iperf3_data.data[ATTR_VERSION],
        }

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DATA_UPDATED, self._schedule_immediate_update
            )
        )

        state = await self.async_get_last_state()
        if not state:
            return
        self._attr_native_value = state.state

    def update(self):
        """Get the latest data and update the states."""
        data = self._iperf3_data.data.get(self.entity_description.key)
        if data is not None:
            self._attr_native_value = round(data, 2)

    @callback
    def _schedule_immediate_update(self, host):
        if host == self._iperf3_data.host:
            self.async_schedule_update_ha_state(True)
