"""Platform for sensor integration."""
from ziggonext import ZiggoNext

from homeassistant.helpers.entity import Entity

from .const import ZIGGO_API


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the sensor platform."""
    # We only want this platform to be set up via discovery.
    sensors = []
    api = hass.data[ZIGGO_API]
    for box_id in api.settopBoxes.keys():
        sensors.append(ZiggoSensor(box_id, api))
    async_add_devices(sensors, update_before_add=True)


class ZiggoSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, boxId, api: ZiggoNext):
        """Initialize the sensor."""
        self._box_id = boxId
        self._box = api.settopBoxes[boxId]
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._box.name + " channel"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._box.info is not None:
            return self._box.info.channelTitle
        return None

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._box = self._api.settopBoxes[self._box_id]

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._box_id + "_channel"
