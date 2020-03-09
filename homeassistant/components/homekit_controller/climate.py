"""Support for Homekit climate devices."""
import logging

from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.climate import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    ClimateDevice,
)
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)

# Map of Homekit operation modes to hass modes
MODE_HOMEKIT_TO_HASS = {
    0: HVAC_MODE_OFF,
    1: HVAC_MODE_HEAT,
    2: HVAC_MODE_COOL,
    3: HVAC_MODE_HEAT_COOL,
}

# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}

DEFAULT_VALID_MODES = list(MODE_HOMEKIT_TO_HASS)

CURRENT_MODE_HOMEKIT_TO_HASS = {
    0: CURRENT_HVAC_IDLE,
    1: CURRENT_HVAC_HEAT,
    2: CURRENT_HVAC_COOL,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit climate."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        if service["stype"] != "thermostat":
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([HomeKitClimateDevice(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitClimateDevice(HomeKitEntity, ClimateDevice):
    """Representation of a Homekit climate device."""

    def __init__(self, *args):
        """Initialise the device."""
        self._state = None
        self._target_mode = None
        self._current_mode = None
        self._valid_modes = []
        self._current_temp = None
        self._target_temp = None
        self._current_humidity = None
        self._target_humidity = None
        self._min_target_temp = None
        self._max_target_temp = None
        self._min_target_humidity = DEFAULT_MIN_HUMIDITY
        self._max_target_humidity = DEFAULT_MAX_HUMIDITY
        super().__init__(*args)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.HEATING_COOLING_CURRENT,
            CharacteristicsTypes.HEATING_COOLING_TARGET,
            CharacteristicsTypes.TEMPERATURE_CURRENT,
            CharacteristicsTypes.TEMPERATURE_TARGET,
            CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT,
            CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET,
        ]

    def _setup_heating_cooling_target(self, characteristic):
        if "valid-values" in characteristic:
            valid_values = [
                val
                for val in DEFAULT_VALID_MODES
                if val in characteristic["valid-values"]
            ]
        else:
            valid_values = DEFAULT_VALID_MODES
            if "minValue" in characteristic:
                valid_values = [
                    val for val in valid_values if val >= characteristic["minValue"]
                ]
            if "maxValue" in characteristic:
                valid_values = [
                    val for val in valid_values if val <= characteristic["maxValue"]
                ]

        self._valid_modes = [MODE_HOMEKIT_TO_HASS[mode] for mode in valid_values]

    def _setup_temperature_target(self, characteristic):
        self._features |= SUPPORT_TARGET_TEMPERATURE

        if "minValue" in characteristic:
            self._min_target_temp = characteristic["minValue"]

        if "maxValue" in characteristic:
            self._max_target_temp = characteristic["maxValue"]

    def _setup_relative_humidity_target(self, characteristic):
        self._features |= SUPPORT_TARGET_HUMIDITY

        if "minValue" in characteristic:
            self._min_target_humidity = characteristic["minValue"]

        if "maxValue" in characteristic:
            self._max_target_humidity = characteristic["maxValue"]

    def _update_heating_cooling_current(self, value):
        # This characteristic describes the current mode of a device,
        # e.g. a thermostat is "heating" a room to 75 degrees Fahrenheit.
        # Can be 0 - 2 (Off, Heat, Cool)
        self._current_mode = CURRENT_MODE_HOMEKIT_TO_HASS.get(value)

    def _update_heating_cooling_target(self, value):
        # This characteristic describes the target mode
        # E.g. should the device start heating a room if the temperature
        # falls below the target temperature.
        # Can be 0 - 3 (Off, Heat, Cool, Auto)
        self._target_mode = MODE_HOMEKIT_TO_HASS.get(value)

    def _update_temperature_current(self, value):
        self._current_temp = value

    def _update_temperature_target(self, value):
        self._target_temp = value

    def _update_relative_humidity_current(self, value):
        self._current_humidity = value

    def _update_relative_humidity_target(self, value):
        self._target_humidity = value

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        characteristics = [
            {"aid": self._aid, "iid": self._chars["temperature.target"], "value": temp}
        ]
        await self._accessory.put_characteristics(characteristics)

    async def async_set_humidity(self, humidity):
        """Set new target humidity."""
        characteristics = [
            {
                "aid": self._aid,
                "iid": self._chars["relative-humidity.target"],
                "value": humidity,
            }
        ]
        await self._accessory.put_characteristics(characteristics)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        characteristics = [
            {
                "aid": self._aid,
                "iid": self._chars["heating-cooling.target"],
                "value": MODE_HASS_TO_HOMEKIT[hvac_mode],
            }
        ]
        await self._accessory.put_characteristics(characteristics)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temp

    @property
    def min_temp(self):
        """Return the minimum target temp."""
        if self._max_target_temp:
            return self._min_target_temp
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum target temp."""
        if self._max_target_temp:
            return self._max_target_temp
        return super().max_temp

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return self._min_target_humidity

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return self._max_target_humidity

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        return self._current_mode

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        return self._target_mode

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return self._valid_modes

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._features

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
