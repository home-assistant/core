"""
Sensor for getting daily kwh usage information from Florida Power & Light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fpl/
"""
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity

CONF_ATTRIBUTION = "Data provided by fpl.com"

DATA_FPL = 'fpl_data'
DEPENDENCIES = ['fpl']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the FPL sensors."""
    if discovery_info is None:
        return

    sensors = []

    if 'yesterday_kwh' in discovery_info:
        sensors.append(FplSensor(
            hass.data[DATA_FPL], 'yesterday_kwh', 'Yesterday', 'kWh'))
    if 'yesterday_dollars' in discovery_info:
        sensors.append(FplSensor(
            hass.data[DATA_FPL], 'yesterday_dollars', 'Yesterday', 'USD'))
    if 'mtd_kwh' in discovery_info:
        sensors.append(FplSensor(
            hass.data[DATA_FPL], 'mtd_kwh', 'Month to Date', 'kWh'))
    if 'mtd_dollars' in discovery_info:
        sensors.append(FplSensor(
            hass.data[DATA_FPL], 'mtd_dollars', 'Month to Date', 'USD'))

    add_devices(sensors, True)


class FplSensor(Entity):
    """An FPL sensor."""

    def __init__(self, fpl_api, sensor_key, range, unit):
        """Initialize the sensor."""
        self._sensor_key = sensor_key
        self._name = "FPL {} {}".format(range, unit)
        self._unit_of_measurement = unit
        self.fpl_api = fpl_api

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self.fpl_api.client, self._sensor_key)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self._unit_of_measurement == "kWh":
            return "mdi:flash"
        else:
            return "mdi:currency-usd"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION
        }

    async def async_update(self):
        """Get the latest state of the sensor."""
        await self.fpl_api.async_update()
