"""Support for Insteon Thermostats via ISY994 Platform."""
from typing import Callable, List, Optional

from pyisy.constants import (
    CMD_CLIMATE_FAN_SETTING,
    CMD_CLIMATE_MODE,
    ISY_VALUE_UNKNOWN,
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
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    _LOGGER,
    DOMAIN as ISY994_DOMAIN,
    HA_FAN_TO_ISY,
    HA_HVAC_TO_ISY,
    ISY994_NODES,
    ISY_HVAC_MODES,
    UOM_TO_STATES,
)
from .entity import ISYNodeEntity
from .helpers import migrate_old_unique_ids

ISY_SUPPORTED_FEATURES = (
    SUPPORT_FAN_MODE | SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_TEMPERATURE_RANGE
)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[list], None],
) -> bool:
    """Set up the ISY994 thermostat platform."""
    devices = []

    hass_isy_data = hass.data[ISY994_DOMAIN][entry.entry_id]
    for node in hass_isy_data[ISY994_NODES][CLIMATE]:
        devices.append(ISYThermostatEntity(node))

    await migrate_old_unique_ids(hass, CLIMATE, devices)
    async_add_entities(devices)


def fix_temp(temp, uom, prec) -> float:
    """Fix Insteon Thermostats' Reported Temperature.

    Insteon Thermostats report temperature in 0.5-deg precision as an int
    by sending a value of 2 times the Temp. Correct by dividing by 2 here.

    Z-Wave Thermostats report temps in tenths as an integer and precision.
    Correct by shifting the decimal place left by the value of prec.
    """
    if temp is None or temp == ISY_VALUE_UNKNOWN:
        return None
    if uom in ["101", "degrees"]:
        return round(int(temp) / 2.0, 1)
    if prec is not None and prec != "0":
        return round(float(temp) * pow(10, -int(prec)), int(prec))
    return int(temp)


class ISYThermostatEntity(ISYNodeEntity, ClimateEntity):
    """Representation of an ISY994 thermostat device."""

    def __init__(self, node) -> None:
        """Initialize the ISY Thermostat Device."""
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
    def supported_features(self):
        """Return the list of supported features."""
        return ISY_SUPPORTED_FEATURES

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_TENTHS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._node.aux_properties.get(PROP_UOM):
            if self._node.aux_properties[PROP_UOM].value == 1:
                return TEMP_CELSIUS
            if self._node.aux_properties[PROP_UOM].value == 2:
                return TEMP_FAHRENHEIT
        return self.hass.config.units.temperature_unit

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if self._node.aux_properties.get(PROP_HUMIDITY):
            return int(self._node.aux_properties[PROP_HUMIDITY].value)
        return None

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        if self._node.aux_properties.get(CMD_CLIMATE_MODE) is not None:
            # Which state values used depends on the mode property's UOM:
            uom = self._node.aux_properties[CMD_CLIMATE_MODE].uom
            # Handle special case for ISYv4 Firmware:
            if uom == "n/a":
                uom = "98" if self._node.protocol == PROTO_INSTEON else "67"
            return UOM_TO_STATES[uom].get(
                self._node.aux_properties[CMD_CLIMATE_MODE].value
            )
        return None

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return ISY_HVAC_MODES

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation if supported."""
        if self._node.aux_properties.get(PROP_HEAT_COOL_STATE):
            return UOM_TO_STATES["66"].get(
                self._node.aux_properties[PROP_HEAT_COOL_STATE].value
            )
        return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return fix_temp(self._node.status, self._uom, self._node.prec)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVAC_MODE_COOL:
            return self.target_temperature_high
        if self.hvac_mode == HVAC_MODE_HEAT:
            return self.target_temperature_low
        return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        target = self._node.aux_properties.get(PROP_SETPOINT_COOL)
        if target:
            return fix_temp(target.value, target.uom, target.prec)
        return None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        target = self._node.aux_properties.get(PROP_SETPOINT_HEAT)
        if target:
            return fix_temp(target.value, target.uom, target.prec)
        return None

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [FAN_AUTO, FAN_ON]

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode ie. auto, on."""
        if self._node.aux_properties.get(CMD_CLIMATE_FAN_SETTING):
            return UOM_TO_STATES["99"].get(
                self._node.aux_properties[CMD_CLIMATE_FAN_SETTING].value
            )
        return None

    def set_temperature(self, **kwargs):
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

    def set_fan_mode(self, fan_mode):
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
