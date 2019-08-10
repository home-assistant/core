"""Support for Homekit sensors."""
from homeassistant.const import TEMP_CELSIUS

from . import KNOWN_DEVICES, HomeKitEntity

HUMIDITY_ICON = "mdi:water-percent"
TEMP_C_ICON = "mdi:thermometer"
BRIGHTNESS_ICON = "mdi:brightness-6"

UNIT_PERCENT = "%"
UNIT_LUX = "lux"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Legacy set up platform."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit covers."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    def async_add_service(aid, service):
        devtype = service["stype"]
        info = {"aid": aid, "iid": service["iid"]}
        if devtype == "humidity":
            async_add_entities([HomeKitHumiditySensor(conn, info)], True)
            return True

        if devtype == "temperature":
            async_add_entities([HomeKitTemperatureSensor(conn, info)], True)
            return True

        if devtype == "light":
            async_add_entities([HomeKitLightSensor(conn, info)], True)
            return True

        return False

    conn.add_listener(async_add_service)


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

        return [CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT]

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

        return [CharacteristicsTypes.TEMPERATURE_CURRENT]

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

        return [CharacteristicsTypes.LIGHT_LEVEL_CURRENT]

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
