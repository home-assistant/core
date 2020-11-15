"""Support for Homekit climate devices."""
import logging

from aiohomekit.model.characteristics import (
    ActivationStateValues,
    CharacteristicsTypes,
    CurrentHeaterCoolerStateValues,
    HeatingCoolingCurrentValues,
    HeatingCoolingTargetValues,
    SwingModeValues,
    TargetHeaterCoolerStateValues,
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
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_OFF,
    SWING_VERTICAL,
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

CURRENT_MODE_HOMEKIT_TO_HASS = {
    HeatingCoolingCurrentValues.IDLE: CURRENT_HVAC_IDLE,
    HeatingCoolingCurrentValues.HEATING: CURRENT_HVAC_HEAT,
    HeatingCoolingCurrentValues.COOLING: CURRENT_HVAC_COOL,
}

SWING_MODE_HOMEKIT_TO_HASS = {
    SwingModeValues.DISABLED: SWING_OFF,
    SwingModeValues.ENABLED: SWING_VERTICAL,
}

CURRENT_HEATER_COOLER_STATE_HOMEKIT_TO_HASS = {
    CurrentHeaterCoolerStateValues.INACTIVE: CURRENT_HVAC_OFF,
    CurrentHeaterCoolerStateValues.IDLE: CURRENT_HVAC_IDLE,
    CurrentHeaterCoolerStateValues.HEATING: CURRENT_HVAC_HEAT,
    CurrentHeaterCoolerStateValues.COOLING: CURRENT_HVAC_COOL,
}

TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS = {
    TargetHeaterCoolerStateValues.AUTOMATIC: HVAC_MODE_HEAT_COOL,
    TargetHeaterCoolerStateValues.HEAT: HVAC_MODE_HEAT,
    TargetHeaterCoolerStateValues.COOL: HVAC_MODE_COOL,
}

# Map of hass operation modes to homekit modes
MODE_HASS_TO_HOMEKIT = {v: k for k, v in MODE_HOMEKIT_TO_HASS.items()}

TARGET_HEATER_COOLER_STATE_HASS_TO_HOMEKIT = {
    v: k for k, v in TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.items()
}

SWING_MODE_HASS_TO_HOMEKIT = {v: k for k, v in SWING_MODE_HOMEKIT_TO_HASS.items()}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit climate."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        entity_class = ENTITY_TYPES.get(service["stype"])
        if not entity_class:
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitHeaterCoolerEntity(HomeKitEntity, ClimateEntity):
    """Representation of a Homekit climate device."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.ACTIVE,
            CharacteristicsTypes.CURRENT_HEATER_COOLER_STATE,
            CharacteristicsTypes.TARGET_HEATER_COOLER_STATE,
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD,
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD,
            CharacteristicsTypes.SWING_MODE,
            CharacteristicsTypes.TEMPERATURE_CURRENT,
        ]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD: temp}
            )
        elif state == TargetHeaterCoolerStateValues.HEAT:
            await self.async_put_characteristics(
                {CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD: temp}
            )
        else:
            hvac_mode = TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.get(state)
            _LOGGER.warning(
                "HomeKit device %s: Setting temperature in %s mode is not supported yet."
                " Consider raising a ticket if you have this device and want to help us implement this feature.",
                self.entity_id,
                hvac_mode,
            )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_put_characteristics(
                {CharacteristicsTypes.ACTIVE: ActivationStateValues.INACTIVE}
            )
            return
        if hvac_mode not in {HVAC_MODE_HEAT, HVAC_MODE_COOL}:
            _LOGGER.warning(
                "HomeKit device %s: Setting temperature in %s mode is not supported yet."
                " Consider raising a ticket if you have this device and want to help us implement this feature.",
                self.entity_id,
                hvac_mode,
            )
        await self.async_put_characteristics(
            {
                CharacteristicsTypes.TARGET_HEATER_COOLER_STATE: TARGET_HEATER_COOLER_STATE_HASS_TO_HOMEKIT[
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
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL:
            return self.service.value(
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            )
        if state == TargetHeaterCoolerStateValues.HEAT:
            return self.service.value(
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            )
        return None

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL and self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ):
            return self.service[
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            ].minStep
        if state == TargetHeaterCoolerStateValues.HEAT and self.service.has(
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
        ):
            return self.service[
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            ].minStep
        return None

    @property
    def min_temp(self):
        """Return the minimum target temp."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL and self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ):
            return self.service[
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            ].minValue
        if state == TargetHeaterCoolerStateValues.HEAT and self.service.has(
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
        ):
            return self.service[
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            ].minValue
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum target temp."""
        state = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        if state == TargetHeaterCoolerStateValues.COOL and self.service.has(
            CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
        ):
            return self.service[
                CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD
            ].maxValue
        if state == TargetHeaterCoolerStateValues.HEAT and self.service.has(
            CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
        ):
            return self.service[
                CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD
            ].maxValue
        return super().max_temp

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        # This characteristic describes the current mode of a device,
        # e.g. a thermostat is "heating" a room to 75 degrees Fahrenheit.
        # Can be 0 - 3 (Off, Idle, Heat, Cool)
        if (
            self.service.value(CharacteristicsTypes.ACTIVE)
            == ActivationStateValues.INACTIVE
        ):
            return CURRENT_HVAC_OFF
        value = self.service.value(CharacteristicsTypes.CURRENT_HEATER_COOLER_STATE)
        return CURRENT_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.get(value)

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        # This characteristic describes the target mode
        # E.g. should the device start heating a room if the temperature
        # falls below the target temperature.
        # Can be 0 - 2 (Auto, Heat, Cool)
        if (
            self.service.value(CharacteristicsTypes.ACTIVE)
            == ActivationStateValues.INACTIVE
        ):
            return HVAC_MODE_OFF
        value = self.service.value(CharacteristicsTypes.TARGET_HEATER_COOLER_STATE)
        return TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS.get(value)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        valid_values = clamp_enum_to_char(
            TargetHeaterCoolerStateValues,
            self.service[CharacteristicsTypes.TARGET_HEATER_COOLER_STATE],
        )
        modes = [
            TARGET_HEATER_COOLER_STATE_HOMEKIT_TO_HASS[mode] for mode in valid_values
        ]
        modes.append(HVAC_MODE_OFF)
        return modes

    @property
    def swing_mode(self):
        """Return the swing setting.

        Requires SUPPORT_SWING_MODE.
        """
        value = self.service.value(CharacteristicsTypes.SWING_MODE)
        return SWING_MODE_HOMEKIT_TO_HASS[value]

    @property
    def swing_modes(self):
        """Return the list of available swing modes.

        Requires SUPPORT_SWING_MODE.
        """
        valid_values = clamp_enum_to_char(
            SwingModeValues,
            self.service[CharacteristicsTypes.SWING_MODE],
        )
        return [SWING_MODE_HOMEKIT_TO_HASS[mode] for mode in valid_values]

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.SWING_MODE: SWING_MODE_HASS_TO_HOMEKIT[swing_mode]}
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = 0

        if self.service.has(CharacteristicsTypes.TEMPERATURE_COOLING_THRESHOLD):
            features |= SUPPORT_TARGET_TEMPERATURE

        if self.service.has(CharacteristicsTypes.TEMPERATURE_HEATING_THRESHOLD):
            features |= SUPPORT_TARGET_TEMPERATURE

        if self.service.has(CharacteristicsTypes.SWING_MODE):
            features |= SUPPORT_SWING_MODE

        return features

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS


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


ENTITY_TYPES = {
    "heater-cooler": HomeKitHeaterCoolerEntity,
    "thermostat": HomeKitClimateEntity,
}
