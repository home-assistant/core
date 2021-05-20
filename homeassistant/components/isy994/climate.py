"""Support for Insteon Thermostats via ISY994 Platform."""
from __future__ import annotations

from pyisy.constants import (
    CMD_CLIMATE_FAN_SETTING,
    CMD_CLIMATE_MODE,
    PROP_HEAT_COOL_STATE,
    PROP_HUMIDITY,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_UOM,
    PROTO_INSTEON,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE,
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    HA_FAN_TO_ISY,
    HA_HVAC_TO_ISY,
    ISY994_NODES,
    ISY_HVAC_MODES,
    UOM_FAN_MODES,
    UOM_HVAC_ACTIONS,
    UOM_HVAC_MODE_GENERIC,
    UOM_HVAC_MODE_INSTEON,
    UOM_ISY_CELSIUS,
    UOM_ISY_FAHRENHEIT,
    UOM_ISYV4_NONE,
    UOM_TO_STATES,
)
from .entity import ISYNodeEntity
from .helpers import convert_isy_value_to_hass, migrate_old_unique_ids

ISY_SUPPORTED_FEATURES = (
    SUPPORT_FAN_MODE | SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_TEMPERATURE_RANGE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the ISY994 thermostat platform."""
    entities = []

    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    for node in hass_isy_data[ISY994_NODES][CLIMATE]:
        entities.append(ISYThermostatEntity(node))

    await migrate_old_unique_ids(hass, CLIMATE, entities)
    async_add_entities(entities)


class ISYThermostatEntity(ISYNodeEntity, ClimateEntity):
    """Representation of an ISY994 thermostat entity."""

    def __init__(self, node) -> None:
        """Initialize the ISY Thermostat entity."""
        super().__init__(node)
        self._node = node
        self._uom = self._node.uom
        if isinstance(self._uom, list):
            self._uom = self._node.uom[0]
        self._hvac_action = None
        self._hvac_mode = None
        self._fan_mode = None
        self._temp_unit = None
        self._current_humidity = 0
        self._target_temp_low = 0
        self._target_temp_high = 0

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return ISY_SUPPORTED_FEATURES

    @property
    def precision(self) -> str:
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        uom = self._node.aux_properties.get(PROP_UOM)
        if not uom:
            return self.hass.config.units.temperature_unit
        if uom.value == UOM_ISY_CELSIUS:
            return TEMP_CELSIUS
        if uom.value == UOM_ISY_FAHRENHEIT:
            return TEMP_FAHRENHEIT

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        humidity = self._node.aux_properties.get(PROP_HUMIDITY)
        if not humidity:
            return None
        return int(humidity.value)

    @property
    def hvac_mode(self) -> str | None:
        """Return hvac operation ie. heat, cool mode."""
        hvac_mode = self._node.aux_properties.get(CMD_CLIMATE_MODE)
        if not hvac_mode:
            return None

        # Which state values used depends on the mode property's UOM:
        uom = hvac_mode.uom
        # Handle special case for ISYv4 Firmware:
        if uom in (UOM_ISYV4_NONE, ""):
            uom = (
                UOM_HVAC_MODE_INSTEON
                if self._node.protocol == PROTO_INSTEON
                else UOM_HVAC_MODE_GENERIC
            )
        return UOM_TO_STATES[uom].get(hvac_mode.value)

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return ISY_HVAC_MODES

    @property
    def hvac_action(self) -> str | None:
        """Return the current running hvac operation if supported."""
        hvac_action = self._node.aux_properties.get(PROP_HEAT_COOL_STATE)
        if not hvac_action:
            return None
        return UOM_TO_STATES[UOM_HVAC_ACTIONS].get(hvac_action.value)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return convert_isy_value_to_hass(
            self._node.status, self._uom, self._node.prec, 1
        )

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return 1.0

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_COOL:
            return self.target_temperature_high
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self.target_temperature_low
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        target = self._node.aux_properties.get(PROP_SETPOINT_COOL)
        if not target:
            return None
        return convert_isy_value_to_hass(target.value, target.uom, target.prec, 1)

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        target = self._node.aux_properties.get(PROP_SETPOINT_HEAT)
        if not target:
            return None
        return convert_isy_value_to_hass(target.value, target.uom, target.prec, 1)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [FAN_AUTO, FAN_ON]

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode ie. auto, on."""
        fan_mode = self._node.aux_properties.get(CMD_CLIMATE_FAN_SETTING)
        if not fan_mode:
            return None
        return UOM_TO_STATES[UOM_FAN_MODES].get(fan_mode.value)

    def set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        target_temp = kwargs.get(ATTR_TEMPERATURE)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp is not None:
            if self.hvac_mode == HVAC_MODE_COOL:
                target_temp_high = target_temp
            if self.hvac_mode == HVAC_MODE_HEAT:
                target_temp_low = target_temp
        if target_temp_low is not None:
            self._node.set_climate_setpoint_heat(int(target_temp_low))
            # Presumptive setting--event stream will correct if cmd fails:
            self._target_temp_low = target_temp_low
        if target_temp_high is not None:
            self._node.set_climate_setpoint_cool(int(target_temp_high))
            # Presumptive setting--event stream will correct if cmd fails:
            self._target_temp_high = target_temp_high
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        _LOGGER.debug("Requested fan mode %s", fan_mode)
        self._node.set_fan_mode(HA_FAN_TO_ISY.get(fan_mode))
        # Presumptive setting--event stream will correct if cmd fails:
        self._fan_mode = fan_mode
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("Requested operation mode %s", hvac_mode)
        self._node.set_climate_mode(HA_HVAC_TO_ISY.get(hvac_mode))
        # Presumptive setting--event stream will correct if cmd fails:
        self._hvac_mode = hvac_mode
        self.schedule_update_ha_state()
