"""Support for Drive sensors."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up an Drive sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a wifi sensor"""
    sensors = []
    network = entry.data.get("networks", "net")
    ssid = network.split(";")[0]
    srn = "ais_wifi_" + ssid
    name = ssid
    # remove if exists
    # if hass.states.get('sensor.ais_wifi_service_current_network_info') is not None:
    #     hass.states.async_remove('sensor.ais_wifi_service_current_network_info')
    #     await hass.async_block_till_done()

    # add new
    sensors.append(WifiSensor(srn, name, "mdi:wifi"))
    async_add_entities(sensors, True)


class WifiSensor(Entity):
    """Implementation of a AIS WiFi sensor."""

    def __init__(self, srn, name, icon):
        """Initialize the Drive sensor."""
        self._icon = icon
        self._srn = srn
        self._data = None
        self._attrs = {}
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        return 1

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "MB"

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        return self._srn

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        pass

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._data = 1
        except KeyError:
            return
