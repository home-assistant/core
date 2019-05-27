"""Support for Myfitnesspal totals as sensors."""
from datetime import date
from homeassistant.const import MASS_GRAMS
from homeassistant.helpers.entity import Entity

# REQUIREMENTS = ['myfitnesspal==1.13.3']
TOTALS = ["sodium", "carbohydrates", "calories", "fat", "sugar", "protein"]
ENERGY_KILOCALORIES = 'kcal'

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set the sensor platform."""
    dev = []
    for resource in TOTALS:

        dev.append(
            MyFitnessPalSensor(resource, config)
        )

    add_devices(dev, True)


class MyFitnessPalSensor(Entity):
    """Representation of a Sensor."""

    ICON = 'mdi:barley'

    def __init__(self, resource, config):
        """Initialize the sensor."""
        self._state = None
        self._user = config['user']
        self._pass = config['pass']
        self._resource = resource

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._resource

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._resource == 'calories':
            return ENERGY_KILOCALORIES
        else:
            return MASS_GRAMS

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        import myfitnesspal
        client = myfitnesspal.Client(self._user, self._pass)

        startdate = date.today()
        mfpday = client.get_date(
            startdate.year, startdate.month, startdate.day)
        if self._resource == 'sodium':
            self._state = int(mfpday.totals[self._resource]) / 1000
        else:
            self._state = int(mfpday.totals[self._resource])
