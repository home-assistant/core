"""
Support for Qwikswitch Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.qwikswitch/
"""
import logging

from homeassistant.components.qwikswitch import DOMAIN as QWIKSWITCH
from homeassistant.helpers.entity import Entity

DEPENDENCIES = [QWIKSWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, _, add_devices, discovery_info=None):
    """Add lights from the main Qwikswitch component."""
    if discovery_info is None:
        return

    qsusb = hass.data[QWIKSWITCH]
    _LOGGER.debug("Setup qwikswitch.sensor %s, %s", qsusb, discovery_info)
    devs = [QSSensor(name, qsid)
            for name, qsid in discovery_info[QWIKSWITCH].items()]
    add_devices(devs)


class QSSensor(Entity):
    """Sensor based on a Qwikswitch relay/dimmer module."""

    _val = {}

    def __init__(self, sensor_name, sensor_id):
        """Initialize the sensor."""
        self._name = sensor_name
        self.qsid = sensor_id

    def update_packet(self, packet):
        """Receive update packet from QSUSB."""
        _LOGGER.debug("Update %s (%s): %s", self.entity_id, self.qsid, packet)
        self._val = packet
        self.async_schedule_update_ha_state()

    @property
    def state(self):
        """Return the value of the sensor."""
        return self._val.get('data', 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._val

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return None

    @property
    def poll(self):
        """QS sensors gets packets in update_packet."""
        return False

    async def async_added_to_hass(self):
        """Listen for updates from QSUSb via dispatcher."""
        # Part of Entity/ToggleEntity
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            self.qsid, self.update_packet)
