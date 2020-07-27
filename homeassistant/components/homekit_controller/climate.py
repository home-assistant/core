"""Support for Homekit climate devices."""
import logging

from aiohomekit.model.characteristics import (
    CharacteristicsTypes,
    HeatingCoolingCurrentValues,
    HeatingCoolingTargetValues,
)
from aiohomekit.utils import clamp_enum_to_char

from homeassistant.components.climate import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    ClimateEntity,
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
    HeatingCoolingTargetValues.OFF: HVAC_MODE_OFF,
    HeatingCoolingTargetValues.HEAT: HVAC_MODE_HEAT,
    HeatingCoolingTargetValues.COOL: HVAC_MODE_COOL,
    HeatingCoolingTargetValues.AUTO: HVAC_MODE_HEAT_COOL,
}

# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}

CURRENT_MODE_HOMEKIT_TO_HASS = {
    HeatingCoolingCurrentValues.IDLE: CURRENT_HVAC_IDLE,
    HeatingCoolingCurrentValues.HEATING: CURRENT_HVAC_HEAT,
    HeatingCoolingCurrentValues.COOLING: CURRENT_HVAC_COOL,
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
        async_add_entities([HomeKitClimateEntity(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitClimateEntity(HomeKitEntity, ClimateEntity):
    """Representation of a Homekit climate device."""

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

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)

        await self.async_put_characteristics(
            {CharacteristicsTypes.TEMPERATURE_TARGET: temp}
        )

    async def async_set_humidity(self, humidity):
        """Set new target humidity."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET: humidity}
        )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        await self.async_put_characteristics(
            {
                CharacteristicsTypes.HEATING_COOLING_TARGET: MODE_HASS_TO_HOMEKIT[
                    hvac_mode
                ],
            }
        )

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_TARGET)

    @property
    def min_temp(self):
        """Return the minimum target temp."""
        if self.service.has(CharacteristicsTypes.TEMPERATURE_TARGET):
            char = self.service[CharacteristicsTypes.TEMPERATURE_TARGET]
            return char.minValue
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum target temp."""
        if self.service.has(CharacteristicsTypes.TEMPERATURE_TARGET):
            char = self.service[CharacteristicsTypes.TEMPERATURE_TARGET]
            return char.maxValue
        return super().max_temp

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET)

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        char = self.service[CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET]
        return char.minValue or DEFAULT_MIN_HUMIDITY

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        char = self.service[CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET]
        return char.maxValue or DEFAULT_MAX_HUMIDITY

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        # This characteristic describes the current mode of a device,
        # e.g. a thermostat is "heating" a room to 75 degrees Fahrenheit.
        # Can be 0 - 2 (Off, Heat, Cool)
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_CURRENT)
        return CURRENT_MODE_HOMEKIT_TO_HASS.get(value)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        # This characteristic describes the target mode
        # E.g. should the device start heating a room if the temperature
        # falls below the target temperature.
        # Can be 0 - 3 (Off, Heat, Cool, Auto)
        value = self.service.value(CharacteristicsTypes.HEATING_COOLING_TARGET)
        return MODE_HOMEKIT_TO_HASS.get(value)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        valid_values = clamp_enum_to_char(
            HeatingCoolingTargetValues,
            self.service[CharacteristicsTypes.HEATING_COOLING_TARGET],
        )
        return [MODE_HOMEKIT_TO_HASS[mode] for mode in valid_values]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = 0

        if self.service.has(CharacteristicsTypes.TEMPERATURE_TARGET):
            features |= SUPPORT_TARGET_TEMPERATURE

        if self.service.has(CharacteristicsTypes.RELATIVE_HUMIDITY_TARGET):
            features |= SUPPORT_TARGET_HUMIDITY

        return features

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS
