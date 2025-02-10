"""Support for climate devices through the SmartThings cloud API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pysmartthings.models import Attribute, Capability, Command

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartThingsConfigEntry, SmartThingsDeviceCoordinator
from .entity import SmartThingsEntity

ATTR_OPERATION_STATE = "operation_state"
MODE_TO_STATE = {
    "auto": HVACMode.HEAT_COOL,
    "cool": HVACMode.COOL,
    "eco": HVACMode.AUTO,
    "rush hour": HVACMode.AUTO,
    "emergency heat": HVACMode.HEAT,
    "heat": HVACMode.HEAT,
    "off": HVACMode.OFF,
}
STATE_TO_MODE = {
    HVACMode.HEAT_COOL: "auto",
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.OFF: "off",
}

OPERATING_STATE_TO_ACTION = {
    "cooling": HVACAction.COOLING,
    "fan only": HVACAction.FAN,
    "heating": HVACAction.HEATING,
    "idle": HVACAction.IDLE,
    "pending cool": HVACAction.COOLING,
    "pending heat": HVACAction.HEATING,
    "vent economizer": HVACAction.FAN,
    "wind": HVACAction.FAN,
}

AC_MODE_TO_STATE = {
    "auto": HVACMode.HEAT_COOL,
    "cool": HVACMode.COOL,
    "dry": HVACMode.DRY,
    "coolClean": HVACMode.COOL,
    "dryClean": HVACMode.DRY,
    "heat": HVACMode.HEAT,
    "heatClean": HVACMode.HEAT,
    "fanOnly": HVACMode.FAN_ONLY,
    "wind": HVACMode.FAN_ONLY,
}
STATE_TO_AC_MODE = {
    HVACMode.HEAT_COOL: "auto",
    HVACMode.COOL: "cool",
    HVACMode.DRY: "dry",
    HVACMode.HEAT: "heat",
    HVACMode.FAN_ONLY: "fanOnly",
}

SWING_TO_FAN_OSCILLATION = {
    SWING_BOTH: "all",
    SWING_HORIZONTAL: "horizontal",
    SWING_VERTICAL: "vertical",
    SWING_OFF: "fixed",
}

FAN_OSCILLATION_TO_SWING = {
    value: key for key, value in SWING_TO_FAN_OSCILLATION.items()
}

WIND = "wind"
WINDFREE = "windFree"

UNIT_MAP = {"C": UnitOfTemperature.CELSIUS, "F": UnitOfTemperature.FAHRENHEIT}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climate entities for a config entry."""
    devices = entry.runtime_data.devices
    ac_capabilities = [
        Capability.AIR_CONDITIONER_MODE,
        Capability.AIR_CONDITIONER_FAN_MODE,
        Capability.SWITCH,
        Capability.TEMPERATURE_MEASUREMENT,
        Capability.THERMOSTAT_COOLING_SETPOINT,
    ]
    async_add_entities(
        SmartThingsAirConditioner(device)
        for device in devices
        if all(capability in device.data for capability in ac_capabilities)
    )

    # broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    # entities: list[ClimateEntity] = []
    # for device in broker.devices.values():
    #     if not broker.any_assigned(device.device_id, CLIMATE_DOMAIN):
    #         continue
    #     if all(capability in device.capabilities for capability in ac_capabilities):
    #         entities.append(SmartThingsAirConditioner(device))
    #     else:
    #         entities.append(SmartThingsThermostat(device))
    # async_add_entities(entities, True)


# def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
#     """Return all capabilities supported if minimum required are present."""
#     supported = [
#         Capability.air_conditioner_mode,
#         Capability.demand_response_load_control,
#         Capability.air_conditioner_fan_mode,
#         Capability.switch,
#         Capability.thermostat,
#         Capability.thermostat_cooling_setpoint,
#         Capability.thermostat_fan_mode,
#         Capability.thermostat_heating_setpoint,
#         Capability.thermostat_mode,
#         Capability.thermostat_operating_state,
#     ]
#     # Can have this legacy/deprecated capability
#     if Capability.thermostat in capabilities:
#         return supported
#     # Or must have all of these thermostat capabilities
#     thermostat_capabilities = [
#         Capability.temperature_measurement,
#         Capability.thermostat_heating_setpoint,
#         Capability.thermostat_mode,
#     ]
#     if all(capability in capabilities for capability in thermostat_capabilities):
#         return supported
#     # Or must have all of these A/C capabilities
#     ac_capabilities = [
#         Capability.air_conditioner_mode,
#         Capability.air_conditioner_fan_mode,
#         Capability.switch,
#         Capability.temperature_measurement,
#         Capability.thermostat_cooling_setpoint,
#     ]
#     if all(capability in capabilities for capability in ac_capabilities):
#         return supported
#     return None


# class SmartThingsThermostat(SmartThingsEntity, ClimateEntity):
#     """Define a SmartThings climate entities."""
#
#     def __init__(self, device):
#         """Init the class."""
#         super().__init__(device)
#         self._attr_supported_features = self._determine_features()
#         self._hvac_mode = None
#         self._hvac_modes = None
#
#     def _determine_features(self):
#         flags = (
#             ClimateEntityFeature.TARGET_TEMPERATURE
#             | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
#             | ClimateEntityFeature.TURN_OFF
#             | ClimateEntityFeature.TURN_ON
#         )
#         if self._device.get_capability(
#             Capability.thermostat_fan_mode, Capability.thermostat
#         ):
#             flags |= ClimateEntityFeature.FAN_MODE
#         return flags
#
#     async def async_set_fan_mode(self, fan_mode: str) -> None:
#         """Set new target fan mode."""
#         await self._device.set_thermostat_fan_mode(fan_mode, set_status=True)
#
#         # State is set optimistically in the command above, therefore update
#         # the entity state ahead of receiving the confirming push updates
#         self.async_schedule_update_ha_state(True)
#
#     async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
#         """Set new target operation mode."""
#         mode = STATE_TO_MODE[hvac_mode]
#         await self._device.set_thermostat_mode(mode, set_status=True)
#
#         # State is set optimistically in the command above, therefore update
#         # the entity state ahead of receiving the confirming push updates
#         self.async_schedule_update_ha_state(True)
#
#     async def async_set_temperature(self, **kwargs: Any) -> None:
#         """Set new operation mode and target temperatures."""
#         # Operation state
#         if operation_state := kwargs.get(ATTR_HVAC_MODE):
#             mode = STATE_TO_MODE[operation_state]
#             await self._device.set_thermostat_mode(mode, set_status=True)
#             await self.async_update()
#
#         # Heat/cool setpoint
#         heating_setpoint = None
#         cooling_setpoint = None
#         if self.hvac_mode == HVACMode.HEAT:
#             heating_setpoint = kwargs.get(ATTR_TEMPERATURE)
#         elif self.hvac_mode == HVACMode.COOL:
#             cooling_setpoint = kwargs.get(ATTR_TEMPERATURE)
#         else:
#             heating_setpoint = kwargs.get(ATTR_TARGET_TEMP_LOW)
#             cooling_setpoint = kwargs.get(ATTR_TARGET_TEMP_HIGH)
#         tasks = []
#         if heating_setpoint is not None:
#             tasks.append(
#                 self._device.set_heating_setpoint(
#                     round(heating_setpoint, 3), set_status=True
#                 )
#             )
#         if cooling_setpoint is not None:
#             tasks.append(
#                 self._device.set_cooling_setpoint(
#                     round(cooling_setpoint, 3), set_status=True
#                 )
#             )
#         await asyncio.gather(*tasks)
#
#         # State is set optimistically in the commands above, therefore update
#         # the entity state ahead of receiving the confirming push updates
#         self.async_schedule_update_ha_state(True)
#
#     async def async_update(self) -> None:
#         """Update the attributes of the climate device."""
#         thermostat_mode = self._device.status.thermostat_mode
#         self._hvac_mode = MODE_TO_STATE.get(thermostat_mode)
#         if self._hvac_mode is None:
#             _LOGGER.debug(
#                 "Device %s (%s) returned an invalid hvac mode: %s",
#                 self._device.label,
#                 self._device.device_id,
#                 thermostat_mode,
#             )
#
#         modes = set()
#         supported_modes = self._device.status.supported_thermostat_modes
#         if isinstance(supported_modes, Iterable):
#             for mode in supported_modes:
#                 if (state := MODE_TO_STATE.get(mode)) is not None:
#                     modes.add(state)
#                 else:
#                     _LOGGER.debug(
#                         (
#                             "Device %s (%s) returned an invalid supported thermostat"
#                             " mode: %s"
#                         ),
#                         self._device.label,
#                         self._device.device_id,
#                         mode,
#                     )
#         else:
#             _LOGGER.debug(
#                 "Device %s (%s) returned invalid supported thermostat modes: %s",
#                 self._device.label,
#                 self._device.device_id,
#                 supported_modes,
#             )
#         self._hvac_modes = list(modes)
#
#     @property
#     def current_humidity(self):
#         """Return the current humidity."""
#         return self._device.status.humidity
#
#     @property
#     def current_temperature(self):
#         """Return the current temperature."""
#         return self._device.status.temperature
#
#     @property
#     def fan_mode(self):
#         """Return the fan setting."""
#         return self._device.status.thermostat_fan_mode
#
#     @property
#     def fan_modes(self):
#         """Return the list of available fan modes."""
#         return self._device.status.supported_thermostat_fan_modes
#
#     @property
#     def hvac_action(self) -> HVACAction | None:
#         """Return the current running hvac operation if supported."""
#         return OPERATING_STATE_TO_ACTION.get(
#             self._device.status.thermostat_operating_state
#         )
#
#     @property
#     def hvac_mode(self) -> HVACMode:
#         """Return current operation ie. heat, cool, idle."""
#         return self._hvac_mode
#
#     @property
#     def hvac_modes(self) -> list[HVACMode]:
#         """Return the list of available operation modes."""
#         return self._hvac_modes
#
#     @property
#     def target_temperature(self):
#         """Return the temperature we try to reach."""
#         if self.hvac_mode == HVACMode.COOL:
#             return self._device.status.cooling_setpoint
#         if self.hvac_mode == HVACMode.HEAT:
#             return self._device.status.heating_setpoint
#         return None
#
#     @property
#     def target_temperature_high(self):
#         """Return the highbound target temperature we try to reach."""
#         if self.hvac_mode == HVACMode.HEAT_COOL:
#             return self._device.status.cooling_setpoint
#         return None
#
#     @property
#     def target_temperature_low(self):
#         """Return the lowbound target temperature we try to reach."""
#         if self.hvac_mode == HVACMode.HEAT_COOL:
#             return self._device.status.heating_setpoint
#         return None
#
#     @property
#     def temperature_unit(self):
#         """Return the unit of measurement."""
#         return UNIT_MAP.get(self._device.status.attributes[Attribute.temperature].unit)


class SmartThingsAirConditioner(SmartThingsEntity, ClimateEntity):
    """Define a SmartThings Air Conditioner."""

    def __init__(self, device: SmartThingsDeviceCoordinator) -> None:
        """Init the class."""
        super().__init__(device)
        self._attr_preset_mode = None
        self._attr_hvac_modes = self._determine_hvac_modes()
        self._attr_preset_modes = self._determine_preset_modes()
        self._attr_swing_modes = self._determine_swing_modes()
        self._attr_supported_features = self._determine_supported_features()

    def _determine_supported_features(self) -> ClimateEntityFeature:
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        if self.supports_capability(Capability.FAN_OSCILLATION_MODE):
            features |= ClimateEntityFeature.SWING_MODE
        if (self._attr_preset_modes is not None) and len(self._attr_preset_modes) > 0:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.AIR_CONDITIONER_FAN_MODE,
            Command.SET_FAN_MODE,
            argument=fan_mode,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return
        tasks = []
        # Turn on the device if it's off before setting mode.
        if not self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH):
            tasks.append(self.async_turn_on())

        mode = STATE_TO_AC_MODE[hvac_mode]
        # If new hvac_mode is HVAC_MODE_FAN_ONLY and AirConditioner support "wind" mode the AirConditioner new mode has to be "wind"
        # The conversion make the mode change working
        # The conversion is made only for device that wrongly has capability "wind" instead "fan_only"
        if hvac_mode == HVACMode.FAN_ONLY:
            if WIND in self._attr_hvac_modes:
                mode = WIND

        tasks.append(
            self.coordinator.client.execute_device_command(
                self.coordinator.device.device_id,
                Capability.AIR_CONDITIONER_MODE,
                Command.SET_AIR_CONDITIONER_MODE,
                argument=mode,
            )
        )
        await asyncio.gather(*tasks)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        tasks = []
        # operation mode
        if operation_mode := kwargs.get(ATTR_HVAC_MODE):
            if operation_mode == HVACMode.OFF:
                tasks.append(self.async_turn_off())
            else:
                if not self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH):
                    tasks.append(self.async_turn_on())
                tasks.append(self.async_set_hvac_mode(operation_mode))
        # temperature
        tasks.append(
            self.coordinator.client.execute_device_command(
                self.coordinator.device.device_id,
                Capability.THERMOSTAT_COOLING_SETPOINT,
                Command.SET_COOLING_SETPOINT,
                argument=kwargs[ATTR_TEMPERATURE],
            )
        )
        await asyncio.gather(*tasks)

    async def async_turn_on(self) -> None:
        """Turn device on."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.SWITCH,
            Command.ON,
        )

    async def async_turn_off(self) -> None:
        """Turn device off."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.SWITCH,
            Command.OFF,
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.get_attribute_value(
            Capability.TEMPERATURE_MEASUREMENT, Attribute.TEMPERATURE
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes.

        Include attributes from the Demand Response Load Control (drlc)
        and Power Consumption capabilities.
        """
        drlc_status = self.get_attribute_value(
            Capability.DEMAND_RESPONSE_LOAD_CONTROL,
            Attribute.DEMAND_RESPONSE_LOAD_CONTROL_STATUS,
        )
        return {
            "drlc_status_duration": drlc_status["duration"],
            "drlc_status_level": drlc_status["drlcLevel"],
            "drlc_status_start": drlc_status["start"],
            "drlc_status_override": drlc_status["override"],
        }

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.FAN_MODE
        )

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.SUPPORTED_AC_FAN_MODES
        )

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, idle."""
        if self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "off":
            return HVACMode.OFF
        return AC_MODE_TO_STATE.get(
            self.get_attribute_value(
                Capability.AIR_CONDITIONER_MODE, Attribute.AIR_CONDITIONER_MODE
            )
        )

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.get_attribute_value(
            Capability.THERMOSTAT_COOLING_SETPOINT, Attribute.COOLING_SETPOINT
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        unit = self.coordinator.data[Capability.TEMPERATURE_MEASUREMENT][
            Attribute.TEMPERATURE
        ].unit
        return UNIT_MAP[unit]

    def _determine_swing_modes(self) -> list[str] | None:
        """Return the list of available swing modes."""
        if (
            supported_modes := self.get_attribute_value(
                Capability.FAN_OSCILLATION_MODE,
                Attribute.SUPPORTED_FAN_OSCILLATION_MODES,
            )
        ) is None:
            return None
        return [FAN_OSCILLATION_TO_SWING.get(m, SWING_OFF) for m in supported_modes]

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set swing mode."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.FAN_OSCILLATION_MODE,
            Command.SET_FAN_OSCILLATION_MODE,
            argument=SWING_TO_FAN_OSCILLATION[swing_mode],
        )

    @property
    def swing_mode(self) -> str:
        """Return the swing setting."""
        return FAN_OSCILLATION_TO_SWING.get(
            self.get_attribute_value(
                Capability.FAN_OSCILLATION_MODE, Attribute.FAN_OSCILLATION_MODE
            ),
            SWING_OFF,
        )

    def _determine_preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        if self.supports_capability(Capability.CUSTOM_AIR_CONDITIONER_OPTIONAL_MODE):
            supported_modes = self.get_attribute_value(
                Capability.CUSTOM_AIR_CONDITIONER_OPTIONAL_MODE,
                Attribute.SUPPORTED_AC_OPTIONAL_MODE,
            )
            if supported_modes and WINDFREE in supported_modes:
                return [WINDFREE]
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set special modes (currently only windFree is supported)."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.CUSTOM_AIR_CONDITIONER_OPTIONAL_MODE,
            Command.SET_AC_OPTIONAL_MODE,
            argument=preset_mode,
        )

    def _determine_hvac_modes(self) -> list[HVACMode]:
        """Determine the supported HVAC modes."""
        modes = {HVACMode.OFF}
        for mode in self.get_attribute_value(
            Capability.AIR_CONDITIONER_MODE, Attribute.SUPPORTED_AC_MODES
        ):
            if (state := AC_MODE_TO_STATE.get(mode)) is not None:
                modes.add(state)
        return list(modes)
