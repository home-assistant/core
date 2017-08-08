""".

Support for Etherrain Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.etherrain/

"""
import logging

from homeassistant.helpers.entity import Entity
import homeassistant.components.etherrain as er

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['etherrain']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup sensor platform."""
    valve_id = config.get("valve_id")
    valve_name = config.get("name")

    add_devices([ERValveSensors(valve_id, valve_name)])


class ERValveSensors(Entity):
    """Representation of an Etherrain valve."""

    def __init__(self, valve_id, valve_name):
        """Init valve sensors."""
        self._valve_id = valve_id
        self._valve_name = valve_name
        self._state = None

    @property
    def name(self):
        """Return valve name."""
        return self._valve_name

    @property
    def state(self):
        """Return valve state."""
        return self._state

    def update(self):
        """Update valve state."""
        self._state = er.get_state(self._valve_id)
        # _LOGGER.info("update etherrain switch {0} - {1}".format(
        # self._valve_id, self._state))

    @property
    def is_on(self):
        """Return valve state."""
        # _LOGGER.info("is_on: etherrain switch {0} - {1}".format(
        # self._valve_id, self._state))
        return self._state
