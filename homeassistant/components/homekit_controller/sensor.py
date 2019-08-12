"""Support for Homekit sensors."""
from homeassistant.const import TEMP_CELSIUS

from . import KNOWN_DEVICES, HomeKitEntity

HUMIDITY_ICON = 'mdi-water-percent'
TEMP_C_ICON = "mdi-temperature-celsius"
BRIGHTNESS_ICON = "mdi-brightness-6"

UNIT_PERCENT = "%"
UNIT_LUX = "lux"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit sensor support."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_DEVICES][discovery_info['serial']]
        devtype = discovery_info['device-type']

        if devtype == 'humidity':
            add_entities(
                [HomeKitHumiditySensor(accessory, discovery_info)], True)
        elif devtype == 'temperature':
            add_entities(
                [HomeKitTemperatureSensor(accessory, discovery_info)], True)
        elif devtype == 'light':
            add_entities(
                [HomeKitLightSensor(accessory, discovery_info)], True)


class HomeKitHumiditySensor(HomeKitEntity):
    """Representation of a Homekit humidity sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._state = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        return [
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT
        ]

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}".format(super().name, "Humidity")

    @property
    def icon(self):
        """Return the sensor icon."""
        return HUMIDITY_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return UNIT_PERCENT

    def _update_relative_humidity_current(self, value):
        self._state = value

    @property
    def state(self):
        """Return the current humidity."""
        return self._state


class HomeKitTemperatureSensor(HomeKitEntity):
    """Representation of a Homekit temperature sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._state = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        return [
            CharacteristicsTypes.TEMPERATURE_CURRENT
        ]

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}".format(super().name, "Temperature")

    @property
    def icon(self):
        """Return the sensor icon."""
        return TEMP_C_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return TEMP_CELSIUS

    def _update_temperature_current(self, value):
        self._state = value

    @property
    def state(self):
        """Return the current temperature in Celsius."""
        return self._state


class HomeKitLightSensor(HomeKitEntity):
    """Representation of a Homekit light level sensor."""

    def __init__(self, *args):
        """Initialise the entity."""
        super().__init__(*args)
        self._state = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes

        return [
            CharacteristicsTypes.LIGHT_LEVEL_CURRENT
        ]

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}".format(super().name, "Light Level")

    @property
    def icon(self):
        """Return the sensor icon."""
        return BRIGHTNESS_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return UNIT_LUX

    def _update_light_level_current(self, value):
        self._state = value

    @property
    def state(self):
        """Return the current light level in lux."""
        return self._state
