"""Support for Kaiterra Temperature ahn Humidity Sensors."""
from homeassistant.const import CONF_DEVICE_ID, CONF_NAME, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DISPATCHER_KAITERRA, DOMAIN

SENSORS = [
    {"name": "Temperature", "prop": "rtemp", "device_class": "temperature"},
    {"name": "Humidity", "prop": "rhumid", "device_class": "humidity"},
]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the kaiterra temperature and humidity sensor."""
    if discovery_info is None:
        return

    api = hass.data[DOMAIN]
    name = discovery_info[CONF_NAME]
    device_id = discovery_info[CONF_DEVICE_ID]

    async_add_entities(
        [KaiterraSensor(api, name, device_id, sensor) for sensor in SENSORS]
    )


class KaiterraSensor(Entity):
    """Implementation of a Kaittera sensor."""

    def __init__(self, api, name, device_id, sensor):
        """Initialize the sensor."""
        self._api = api
        self._name = f'{name} {sensor["name"]}'
        self._device_id = device_id
        self._kind = sensor["name"].lower()
        self._property = sensor["prop"]
        self._device_class = sensor["device_class"]

    @property
    def _sensor(self):
        """Return the sensor data."""
        return self._api.data.get(self._device_id, {}).get(self._property, {})

    @property
    def should_poll(self):
        """Return that the sensor should not be polled."""
        return False

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._api.data.get(self._device_id) is not None

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._sensor.get("value")

    @property
    def unique_id(self):
        """Return the sensor's unique id."""
        return f"{self._device_id}_{self._kind}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if not self._sensor.get("units"):
            return None

        value = self._sensor["units"].value

        if value == "F":
            return TEMP_FAHRENHEIT
        if value == "C":
            return TEMP_CELSIUS
        return value

    async def async_added_to_hass(self):
        """Register callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DISPATCHER_KAITERRA, self.async_write_ha_state
            )
        )
