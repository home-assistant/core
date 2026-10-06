"""Support for the Daikin HVAC."""

from datetime import timedelta
import logging
from typing import Any, Literal, cast, override

from daikin_onecta.models import (
    Characteristic,
    FanDirectionAxis,
    FanOperationMode,
    FanSpeed,
    ManagementPoint,
    Setpoint,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_HOMEKIT_FAN_MODE_ALIASES, DOMAIN, FANMODE_FIXED
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import DaikinOnectaEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

PRESET_MODES = (PRESET_BOOST, PRESET_AWAY, PRESET_COMFORT, PRESET_ECO)

DAIKIN_FAN_MODE_QUIET = "quiet"

HOMEKIT_FIXED_FAN_MODE_ALIASES = {
    FAN_MIDDLE: "2",
    FAN_MEDIUM: "3",
    FAN_HIGH: "5",
}

CLIMATE_ENTITY_DESCRIPTIONS = {
    "calculatedLeavingWaterTemperature": ClimateEntityDescription(
        key="calculated_leaving_water_temperature",
        translation_key="calculated_leaving_water_temperature",
    ),
    "leavingWaterOffset": ClimateEntityDescription(
        key="leaving_water_offset",
        translation_key="leaving_water_offset",
    ),
    "leavingWaterTemperature": ClimateEntityDescription(
        key="leaving_water_temperature",
        translation_key="leaving_water_temperature",
    ),
    "roomTemperature": ClimateEntityDescription(
        key="room_temperature",
        translation_key="room_temperature",
    ),
}

DAIKIN_HVAC_TO_HA = {
    "fanOnly": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "cooling": HVACMode.COOL,
    "heating": HVACMode.HEAT,
    "heatingDay": HVACMode.HEAT,
    "heatingNight": HVACMode.HEAT,
    "auto": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
    "humidification": HVACMode.DRY,
}

HA_PRESET_TO_DAIKIN = {
    PRESET_AWAY: "holidayMode",
    PRESET_NONE: "off",
    PRESET_BOOST: "powerfulMode",
    PRESET_COMFORT: "comfortMode",
    PRESET_ECO: "econoMode",
}

_SENSORY_DATA_MODEL_ATTRIBUTES = {
    "roomTemperature": "room_temperature",
    "leavingWaterTemperature": "leaving_water_temperature",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin climate based on config_entry."""
    coordinator = config_entry.runtime_data
    entities = [
        entity
        for device in (coordinator.data or {}).values()
        for entity in _create_climate_entities(device, coordinator)
    ]
    async_add_entities(entities)


def _create_climate_entities(
    device: DaikinOnectaDevice, coordinator: OnectaDataUpdateCoordinator
) -> list[DaikinClimate]:
    """Create climate entities for all independently controllable zones."""
    entities: list[DaikinClimate] = []
    for management_point in device.device.management_points_by_type("climateControl"):
        modes: list[str] = []
        if management_point.temperature_control is not None:
            for (
                operation_mode
            ) in management_point.temperature_control.value.operation_modes.values():
                modes.extend(operation_mode.setpoints)
        # The setpoints may recur across operation modes, but each management
        # point represents an independently controllable climate zone.
        modes = list(dict.fromkeys(modes))
        entities.extend(
            DaikinClimate(device, mode, coordinator, management_point.embedded_id)
            for mode in modes
        )
    return entities


class DaikinClimate(DaikinOnectaEntity, ClimateEntity):
    """Representation of a Daikin HVAC."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    # Setpoint is the setpoint string under
    # temperatureControl/value/operationsModes/mode/setpoints, for example roomTemperature/leavingWaterOffset
    def __init__(
        self,
        device: DaikinOnectaDevice,
        setpoint: str,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator, device)
        self._embedded_id = embedded_id
        self._setpoint = setpoint
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._setpoint}"
        self.entity_description = CLIMATE_ENTITY_DESCRIPTIONS.get(
            setpoint,
            ClimateEntityDescription(
                key=setpoint,
                translation_key="setpoint",
                translation_placeholders={"setpoint": setpoint},
            ),
        )
        self._update_state()

    def _update_state(self) -> None:
        """Refresh all state attributes from the device."""
        # Successful writes update the typed model optimistically so Home
        # Assistant reflects the new state without waiting for the next poll.
        self._attr_supported_features = self._get_supported_features()
        self._attr_current_temperature = self._get_current_temperature()
        self._attr_max_temp = self._get_max_temp()
        self._attr_min_temp = self._get_min_temp()
        self._attr_target_temperature_step = self._get_target_temperature_step()
        self._attr_target_temperature = self._get_target_temperature()
        self._attr_hvac_modes = self._get_hvac_modes()
        self._attr_swing_modes = self._get_swing_modes()
        self._attr_swing_horizontal_modes = self._get_swing_horizontal_modes()
        self._attr_preset_modes = self._get_preset_modes()
        self._attr_fan_modes = self._get_fan_modes()
        self._attr_hvac_mode = self._get_hvac_mode()
        self._attr_swing_mode = self._get_swing_mode()
        self._attr_swing_horizontal_mode = self._get_swing_horizontal_mode()
        self._attr_preset_mode = self._get_preset_mode()
        self._attr_fan_mode = self._get_fan_mode()

    def _raise_command_failed(self, translation_key: str) -> None:
        """Raise an error when Daikin rejects a command."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )

    async def _async_patch(
        self, characteristic: str, path: str | None, value: Any
    ) -> bool:
        """Patch a climate characteristic through the serialized command gateway."""
        return await self.coordinator.api.async_execute_command(
            lambda client: client.patch_characteristic(
                self._device.id, self._embedded_id, characteristic, value, path=path
            )
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._async_update_device_registry()
        self._update_state()
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return (
            super().available
            and self._device.available
            and self._climate_control() is not None
        )

    def _climate_control(self) -> ManagementPoint | None:
        """Return the typed climate-control management point."""
        return self._device.management_point(self._embedded_id)

    def _operation_mode(self) -> Characteristic[str] | None:
        """Return the operation-mode characteristic."""
        cc = self._climate_control()
        return cc.operation_mode if cc is not None else None

    def _fan_operation(
        self, operation_mode: str | None = None
    ) -> FanOperationMode | None:
        """Return fan controls for an operation mode."""
        cc = self._climate_control()
        if cc is None or cc.fan_control is None:
            return None
        if operation_mode is None:
            if cc.operation_mode is None:
                return None
            operation_mode = cc.operation_mode.value
        return (cc.fan_control.value.operation_modes or {}).get(operation_mode)

    def _preset_characteristic(self, daikin_mode: str) -> Characteristic[Any] | None:
        """Return a preset characteristic by Daikin API name."""
        cc = self._climate_control()
        if cc is None:
            return None
        if daikin_mode == "holidayMode":
            return cc.holiday_mode
        return cc.characteristic(daikin_mode)

    @property
    def _homekit_fan_mode_aliases_enabled(self) -> bool:
        """Return whether HomeKit fan mode aliases are enabled."""
        return bool(
            self.coordinator.config_entry.options.get(
                CONF_HOMEKIT_FAN_MODE_ALIASES, False
            )
        )

    def _homekit_fan_mode_aliases(self, fan_speed: FanSpeed) -> dict[str, str]:
        """Return HomeKit fan mode aliases available for the fan speed data."""
        aliases: dict[str, str] = {}
        if not self._homekit_fan_mode_aliases_enabled:
            return aliases

        current_mode_values = fan_speed.current_mode.values or []
        if DAIKIN_FAN_MODE_QUIET in current_mode_values:
            aliases[FAN_LOW] = DAIKIN_FAN_MODE_QUIET

        if FANMODE_FIXED not in current_mode_values or not fan_speed.modes:
            return aliases
        fixed_mode = fan_speed.modes.get(FANMODE_FIXED)
        if (
            fixed_mode is None
            or fixed_mode.min_value is None
            or fixed_mode.max_value is None
            or fixed_mode.step_value is None
        ):
            return aliases
        fixed_values = {
            str(value)
            for value in range(
                int(fixed_mode.min_value),
                int(fixed_mode.max_value) + 1,
                int(fixed_mode.step_value),
            )
        }
        aliases.update(
            {
                alias: daikin_mode
                for alias, daikin_mode in HOMEKIT_FIXED_FAN_MODE_ALIASES.items()
                if daikin_mode in fixed_values
            }
        )
        return aliases

    def _get_homekit_fan_mode(self, fan_speed: FanSpeed, fan_mode: str) -> str:
        """Return the HomeKit alias for a Daikin fan mode when available."""
        if not self._homekit_fan_mode_aliases_enabled:
            return fan_mode

        aliases = self._homekit_fan_mode_aliases(fan_speed)
        for alias, daikin_mode in aliases.items():
            if fan_mode == daikin_mode:
                return alias

        return fan_mode

    def _resolve_homekit_fan_mode_alias(
        self, fan_speed: FanSpeed, fan_mode: str
    ) -> str:
        """Return the Daikin fan mode represented by a HomeKit alias."""
        return self._homekit_fan_mode_aliases(fan_speed).get(fan_mode, fan_mode)

    def _get_setpoint(self, operation_mode: str | None = None) -> Setpoint | None:
        """Return a setpoint for an operation mode."""
        cc = self._climate_control()
        if cc is None or cc.temperature_control is None:
            return None
        if operation_mode is None:
            if cc.operation_mode is None:
                return None
            operation_mode = cc.operation_mode.value
        mode_setpoints = cc.temperature_control.value.operation_modes.get(
            operation_mode
        )
        if mode_setpoints is None:
            return None
        return mode_setpoints.setpoints.get(self._setpoint)

    def _sensory_data_for_setpoint(
        self, setpoint: str
    ) -> Characteristic[int | float] | None:
        """Return a sensory characteristic by Daikin API name."""
        cc = self._climate_control()
        if cc is None or cc.sensory_data is None:
            return None
        attribute = _SENSORY_DATA_MODEL_ATTRIBUTES.get(setpoint)
        if attribute is None:
            return None
        return cast(
            "Characteristic[int | float] | None",
            getattr(cc.sensory_data.value, attribute),
        )

    def _get_supported_features(self) -> ClimateEntityFeature:
        """Return the features supported by this climate entity."""
        supported_features = (
            ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        )
        setpointdict = self._get_setpoint()
        if setpointdict is not None and setpointdict.settable:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if len(self._get_preset_modes()) > 1:
            supported_features |= ClimateEntityFeature.PRESET_MODE
        cc = self._climate_control()
        if cc is not None:
            fan_operation = self._fan_operation()
            if fan_operation is not None:
                if fan_operation.fan_speed is not None:
                    supported_features |= ClimateEntityFeature.FAN_MODE
                if fan_operation.fan_direction is not None:
                    if fan_operation.fan_direction.vertical is not None:
                        supported_features |= ClimateEntityFeature.SWING_MODE
                    if fan_operation.fan_direction.horizontal is not None:
                        supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

            _LOGGER.debug(
                "Device '%s' supports features %s",
                self._device.name,
                supported_features,
            )

        return supported_features

    def _get_current_temperature(self) -> float | None:
        """Return the current temperature for this setpoint."""
        current_temp: float | None = None
        sensory_data = self._sensory_data_for_setpoint(self._setpoint)
        # Check if there is a sensoryData which is for the same setpoint, if so, return that
        if sensory_data is not None:
            current_temp = sensory_data.value
        else:
            # There is no sensoryData with the same name as the setpoint we are using, see
            # if we are using leavingWaterOffset, at that moment see if we have a
            # leavingWaterTemperature temperature
            lwsensor = self._sensory_data_for_setpoint("leavingWaterTemperature")
            if self._setpoint == "leavingWaterOffset" and lwsensor is not None:
                current_temp = lwsensor.value
        _LOGGER.debug(
            "Device '%s' %s current temperature '%s'",
            self._device.name,
            self._setpoint,
            current_temp,
        )
        return current_temp

    def _get_max_temp(self) -> float:
        """Return the maximum configurable temperature."""
        setpointdict = self._get_setpoint()
        max_temp = (
            setpointdict.max_value
            if setpointdict is not None and setpointdict.max_value is not None
            else super().max_temp
        )
        _LOGGER.debug(
            "Device '%s' %s max temperature '%s'",
            self._device.name,
            self._setpoint,
            max_temp,
        )
        return max_temp

    def _get_min_temp(self) -> float:
        """Return the minimum configurable temperature."""
        setpointdict = self._get_setpoint()
        min_temp = (
            setpointdict.min_value
            if setpointdict is not None and setpointdict.min_value is not None
            else super().min_temp
        )
        _LOGGER.debug(
            "Device '%s' %s min temperature '%s'",
            self._device.name,
            self._setpoint,
            min_temp,
        )
        return min_temp

    def _get_target_temperature(self) -> float | None:
        """Return the configured target temperature."""
        value: float | None = None
        setpointdict = self._get_setpoint()
        if setpointdict is not None:
            value = setpointdict.value
        _LOGGER.debug(
            "Device '%s' %s target temperature '%s'",
            self._device.name,
            self._setpoint,
            value,
        )
        return value

    def _get_target_temperature_step(self) -> float | None:
        """Return the target temperature increment."""
        step_value: float | None = None
        setpointdict = self._get_setpoint()
        if setpointdict is not None:
            step_value = (
                setpointdict.step_value
                if setpointdict.step_value is not None
                else super().target_temperature_step
            )
        _LOGGER.debug(
            "Device '%s' %s target temperature step '%s'",
            self._device.name,
            self._setpoint,
            step_value,
        )
        return step_value

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the HVAC mode and/or target temperature."""
        if ATTR_HVAC_MODE in kwargs:
            await self.async_handle_set_hvac_mode_service(kwargs[ATTR_HVAC_MODE])

        if ATTR_TEMPERATURE in kwargs:
            value = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug(
                "Device '%s' request to set temperature to '%s'",
                self._device.name,
                value,
            )
            if self._attr_target_temperature != value:
                operationmode = self._operation_mode()
                if operationmode is not None:
                    omv = operationmode.value
                    res = await self._async_patch(
                        "temperatureControl",
                        f"/operationModes/{omv}/setpoints/{self._setpoint}",
                        value,
                    )
                    # When updating the value to the daikin cloud worked update our local cached version
                    if res:
                        setpointdict = self._get_setpoint(omv)
                        if setpointdict is not None:
                            setpointdict.value = value
                            self._attr_target_temperature = value
                            self.coordinator.async_update_listeners()
                    else:
                        self._raise_command_failed("set_temperature_failed")

    def _get_hvac_mode(self) -> HVACMode | None:
        """Return current HVAC mode."""
        mode = "off"
        operationmode = self._operation_mode()
        cc = self._climate_control()
        if cc is not None:
            onoff = cc.on_off_mode
            if onoff is not None and onoff.value != "off" and operationmode is not None:
                mode = operationmode.value
            _LOGGER.debug(
                "Device '%s' %s hvac mode '%s'",
                self._device.name,
                self._setpoint,
                mode,
            )
        return DAIKIN_HVAC_TO_HA.get(mode)

    def _get_hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        modes = [HVACMode.OFF]
        operationmode = self._operation_mode()
        if operationmode is not None:
            if operationmode.settable:
                for mode in operationmode.values or []:
                    ha_mode = DAIKIN_HVAC_TO_HA.get(mode)
                    if ha_mode is not None and ha_mode not in modes:
                        modes.append(ha_mode)
            currentmode = operationmode.value
            ha_currentmode = DAIKIN_HVAC_TO_HA.get(currentmode)
            if ha_currentmode is not None and ha_currentmode not in modes:
                modes.append(ha_currentmode)
        return modes

    def _native_hvac_mode(self, hvac_mode: HVACMode) -> str | None:
        """Return an advertised native mode for a requested HVAC mode."""
        operation_mode = self._operation_mode()
        if operation_mode is None:
            return None

        if DAIKIN_HVAC_TO_HA.get(operation_mode.value) == hvac_mode:
            return operation_mode.value

        if not operation_mode.settable:
            return None

        return next(
            (
                mode
                for mode in operation_mode.values or []
                if DAIKIN_HVAC_TO_HA.get(mode) == hvac_mode
            ),
            None,
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        _LOGGER.debug(
            "Device '%s' request to set hvac_mode to '%s'",
            self._device.name,
            hvac_mode,
        )

        # First determine the new settings for onOffMode/operationMode
        on_off_mode = None
        if hvac_mode == HVACMode.OFF:
            if self.hvac_mode != HVACMode.OFF:
                on_off_mode = "off"
        elif self.hvac_mode == HVACMode.OFF:
            on_off_mode = "on"

        cc = self._climate_control()

        # Only set the on/off to Daikin when we need to change it
        if on_off_mode is not None:
            if not await self._async_patch("onOffMode", None, on_off_mode):
                self._raise_command_failed("set_hvac_mode_failed")
            cc = self._climate_control()
            if cc is not None and cc.on_off_mode is not None:
                cc.on_off_mode.value = on_off_mode
                # Publish the confirmed power change before a subsequent
                # operation-mode write, which may be rejected by the cloud.
                self._update_state()
                self.coordinator.async_update_listeners()

        operation_mode = (
            self._native_hvac_mode(hvac_mode) if hvac_mode != HVACMode.OFF else None
        )

        # Only set the advertised operationMode when it has changed.
        if (
            operation_mode is not None
            and cc is not None
            and cc.operation_mode is not None
            and operation_mode != cc.operation_mode.value
        ):
            if not await self._async_patch("operationMode", None, operation_mode):
                self._raise_command_failed("set_hvac_mode_failed")
            cc = self._climate_control()
            if cc is not None and cc.operation_mode is not None:
                cc.operation_mode.value = operation_mode
            # When switching HVAC mode it could be that we can set min/max/target/etc
            # which we couldn't set with a previous HVAC mode.
            self._update_state()
            self.coordinator.async_update_listeners()

    def _get_fan_mode(self) -> str | None:
        """Return the active fan mode."""
        fan_operation = self._fan_operation()
        if fan_operation is None or fan_operation.fan_speed is None:
            return None
        fan_speed = fan_operation.fan_speed
        mode = fan_speed.current_mode.value
        if (
            mode == FANMODE_FIXED
            and fan_speed.modes
            and FANMODE_FIXED in fan_speed.modes
        ):
            mode = str(fan_speed.modes[FANMODE_FIXED].value)
        return self._get_homekit_fan_mode(fan_speed, mode)

    def _get_fan_modes(self) -> list[str]:
        """Return available fan modes."""
        fan_operation = self._fan_operation()
        if fan_operation is None or fan_operation.fan_speed is None:
            return []
        fan_speed = fan_operation.fan_speed
        fan_modes: list[str] = []
        for mode in fan_speed.current_mode.values or []:
            if (
                mode == FANMODE_FIXED
                and fan_speed.modes
                and FANMODE_FIXED in fan_speed.modes
            ):
                fixed = fan_speed.modes[FANMODE_FIXED]
                if (
                    fixed.min_value is not None
                    and fixed.max_value is not None
                    and fixed.step_value is not None
                ):
                    fan_modes.extend(
                        str(value)
                        for value in range(
                            int(fixed.min_value),
                            int(fixed.max_value) + 1,
                            int(fixed.step_value),
                        )
                    )
            else:
                fan_modes.append(mode)
        for alias in self._homekit_fan_mode_aliases(fan_speed):
            if alias not in fan_modes:
                fan_modes.append(alias)
        return fan_modes

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        requested_fan_mode = str(fan_mode)
        fan_operation = self._fan_operation()
        cc = self._climate_control()
        if (
            fan_operation is None
            or fan_operation.fan_speed is None
            or cc is None
            or cc.operation_mode is None
        ):
            return
        fan_speed = fan_operation.fan_speed
        operation_mode = cc.operation_mode.value
        fan_mode = self._resolve_homekit_fan_mode_alias(fan_speed, requested_fan_mode)
        if fan_mode.isnumeric():
            if fan_speed.current_mode.value != FANMODE_FIXED:
                if not await self._async_patch(
                    "fanControl",
                    f"/operationModes/{operation_mode}/fanSpeed/currentMode",
                    FANMODE_FIXED,
                ):
                    self._raise_command_failed("set_fan_mode_failed")
                fan_operation = self._fan_operation(operation_mode)
                if fan_operation is None or fan_operation.fan_speed is None:
                    return
                fan_speed = fan_operation.fan_speed
                fan_speed.current_mode.value = FANMODE_FIXED
                # The fan is already in fixed mode even if the following speed
                # write fails, so publish this confirmed intermediate state.
                self._attr_fan_mode = self._get_fan_mode()
                self.coordinator.async_update_listeners()
            fixed = fan_speed.modes.get(FANMODE_FIXED) if fan_speed.modes else None
            new_fixed_mode = int(fan_mode)
            if fixed is not None and fixed.value != new_fixed_mode:
                if not await self._async_patch(
                    "fanControl",
                    f"/operationModes/{operation_mode}/fanSpeed/modes/fixed",
                    new_fixed_mode,
                ):
                    self._raise_command_failed("set_fan_mode_failed")
                fan_operation = self._fan_operation(operation_mode)
                if fan_operation is None or fan_operation.fan_speed is None:
                    return
                fan_speed = fan_operation.fan_speed
                fixed = fan_speed.modes.get(FANMODE_FIXED) if fan_speed.modes else None
                if fixed is None:
                    return
                fixed.value = new_fixed_mode
        elif fan_speed.current_mode.value != fan_mode:
            if not await self._async_patch(
                "fanControl",
                f"/operationModes/{operation_mode}/fanSpeed/currentMode",
                fan_mode,
            ):
                self._raise_command_failed("set_fan_mode_failed")
            fan_operation = self._fan_operation(operation_mode)
            if fan_operation is None or fan_operation.fan_speed is None:
                return
            fan_speed = fan_operation.fan_speed
            fan_speed.current_mode.value = fan_mode

        self._attr_fan_mode = self._get_fan_mode()
        self.coordinator.async_update_listeners()

    def _get_swing_mode_for_direction(
        self, direction: Literal["vertical", "horizontal"]
    ) -> str:
        """Return current swing mode for an axis."""
        fan_operation = self._fan_operation()
        if fan_operation is None or fan_operation.fan_direction is None:
            return ""
        axis = cast(
            "FanDirectionAxis | None", getattr(fan_operation.fan_direction, direction)
        )
        return axis.current_mode.value.lower() if axis is not None else ""

    def _get_swing_mode(self) -> str:
        """Return the vertical swing mode."""
        return self._get_swing_mode_for_direction("vertical")

    def _get_swing_horizontal_mode(self) -> str:
        """Return the horizontal swing mode."""
        return self._get_swing_mode_for_direction("horizontal")

    def _get_swing_modes_for_direction(
        self, direction: Literal["vertical", "horizontal"]
    ) -> list[str]:
        """Return supported swing modes for an axis."""
        fan_operation = self._fan_operation()
        if fan_operation is None or fan_operation.fan_direction is None:
            return []
        axis = cast(
            "FanDirectionAxis | None", getattr(fan_operation.fan_direction, direction)
        )
        if axis is None:
            return []
        return [mode.lower() for mode in axis.current_mode.values or []]

    def _get_swing_modes(self) -> list[str]:
        """Return the supported vertical swing modes."""
        return self._get_swing_modes_for_direction("vertical")

    def _get_swing_horizontal_modes(self) -> list[str]:
        """Return the supported horizontal swing modes."""
        return self._get_swing_modes_for_direction("horizontal")

    async def _async_set_swing(
        self, direction: Literal["vertical", "horizontal"], swing_mode: str
    ) -> bool:
        """Set a fan-direction mode."""
        fan_operation = self._fan_operation()
        cc = self._climate_control()
        if (
            fan_operation is None
            or fan_operation.fan_direction is None
            or cc is None
            or cc.operation_mode is None
        ):
            return False
        axis = cast(
            "FanDirectionAxis | None", getattr(fan_operation.fan_direction, direction)
        )
        if axis is None:
            return False
        new_mode = next(
            (
                mode
                for mode in axis.current_mode.values or []
                if swing_mode == mode.lower()
            ),
            None,
        )
        if new_mode is None:
            return False
        operation_mode = cc.operation_mode.value
        result = await self._async_patch(
            "fanControl",
            f"/operationModes/{operation_mode}/fanDirection/{direction}/currentMode",
            new_mode,
        )
        if result:
            fan_operation = self._fan_operation(operation_mode)
            if fan_operation is not None and fan_operation.fan_direction is not None:
                axis = cast(
                    "FanDirectionAxis | None",
                    getattr(fan_operation.fan_direction, direction),
                )
                if axis is not None:
                    axis.current_mode.value = new_mode
        return result

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode."""
        res = True
        if self.swing_mode != swing_mode:
            res = await self._async_set_swing("vertical", swing_mode)

            if res is True:
                self._attr_swing_mode = swing_mode
                self.coordinator.async_update_listeners()
            else:
                self._raise_command_failed("set_swing_mode_failed")
        else:
            _LOGGER.debug(
                "Device '%s' request to set vertical swing mode '%s' ignored already set",
                self._device.name,
                swing_mode,
            )

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the horizontal swing mode."""
        res = True
        if self.swing_horizontal_mode != swing_horizontal_mode:
            res = await self._async_set_swing("horizontal", swing_horizontal_mode)

            if res is True:
                self._attr_swing_horizontal_mode = swing_horizontal_mode
                self.coordinator.async_update_listeners()
            else:
                self._raise_command_failed("set_swing_mode_failed")
        else:
            _LOGGER.debug(
                "Device '%s' request to set horizontal swing mode '%s' ignored already set",
                self._device.name,
                swing_horizontal_mode,
            )

    def _get_preset_mode(self) -> str:
        """Return the active preset mode."""
        for mode in PRESET_MODES:
            preset = self._preset_characteristic(HA_PRESET_TO_DAIKIN[mode])
            if preset is None:
                continue
            if mode == PRESET_AWAY:
                if preset.value.enabled:
                    return mode
            elif preset.value == "on":
                return mode
        return PRESET_NONE

    async def _async_disable_preset_mode(self, preset_mode: str) -> bool:
        """Disable the current Daikin preset mode."""
        daikin_mode = HA_PRESET_TO_DAIKIN[preset_mode]
        if preset_mode == PRESET_AWAY:
            result = await self.coordinator.api.async_execute_command(
                lambda client: client.set_holiday_mode(
                    self._device.id, self._embedded_id, False
                )
            )
        else:
            result = await self._async_patch(daikin_mode, None, "off")
        if result:
            preset = self._preset_characteristic(daikin_mode)
            if preset_mode == PRESET_AWAY and preset is not None:
                preset.value.enabled = False
            elif preset is not None:
                preset.value = "off"
        return result

    async def _async_enable_preset_mode(self, preset_mode: str) -> bool:
        """Enable the requested Daikin preset mode."""
        daikin_mode = HA_PRESET_TO_DAIKIN[preset_mode]
        if self.hvac_mode == HVACMode.OFF and preset_mode == PRESET_BOOST:
            await self.async_turn_on()
            if self.hvac_mode == HVACMode.OFF:
                return False
        if preset_mode == PRESET_AWAY:
            today = dt_util.now().date()
            result = await self.coordinator.api.async_execute_command(
                lambda client: client.set_holiday_mode(
                    self._device.id,
                    self._embedded_id,
                    True,
                    start_date=today,
                    end_date=today + timedelta(days=60),
                )
            )
        else:
            result = await self._async_patch(daikin_mode, None, "on")
        if result:
            preset = self._preset_characteristic(daikin_mode)
            if preset_mode == PRESET_AWAY and preset is not None:
                preset.value.enabled = True
            elif preset is not None:
                preset.value = "on"
        return result

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the active preset mode."""
        _LOGGER.debug(
            "Device '%s' request set preset mode %s", self._device.name, preset_mode
        )
        if (current_preset := self.preset_mode) not in (None, PRESET_NONE):
            if not await self._async_disable_preset_mode(current_preset):
                self._raise_command_failed("set_preset_mode_failed")
            self._update_state()
            self.coordinator.async_update_listeners()

        if preset_mode != PRESET_NONE:
            if not await self._async_enable_preset_mode(preset_mode):
                self._raise_command_failed("set_preset_mode_failed")
            self._update_state()
            self.coordinator.async_update_listeners()

    def _get_preset_modes(self) -> list[str]:
        """Return supported preset modes."""
        supported = [PRESET_NONE]
        supported.extend(
            mode
            for mode in PRESET_MODES
            if self._preset_characteristic(HA_PRESET_TO_DAIKIN[mode]) is not None
        )
        supported.sort()
        return supported

    @override
    async def async_turn_on(self) -> None:
        """Turn device CLIMATE on."""
        _LOGGER.debug("Device '%s' request to turn on", self._device.name)
        cc = self._climate_control()
        result = True
        if (
            cc is not None
            and cc.on_off_mode is not None
            and cc.on_off_mode.value == "off"
        ):
            result &= await self._async_patch("onOffMode", None, "on")
            if result is False:
                self._raise_command_failed("turn_on_failed")
            else:
                cc = self._climate_control()
                if cc is None or cc.on_off_mode is None:
                    return
                cc.on_off_mode.value = "on"
                self._attr_hvac_mode = self._get_hvac_mode()
                self.coordinator.async_update_listeners()
        else:
            _LOGGER.debug(
                "Device '%s' request to turn on ignored because device is already on",
                self._device.name,
            )

    @override
    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        _LOGGER.debug("Device '%s' request to turn off", self._device.name)
        cc = self._climate_control()
        result = True
        if (
            cc is not None
            and cc.on_off_mode is not None
            and cc.on_off_mode.value == "on"
        ):
            result &= await self._async_patch("onOffMode", None, "off")
            if result is False:
                self._raise_command_failed("turn_off_failed")
            else:
                cc = self._climate_control()
                if cc is None or cc.on_off_mode is None:
                    return
                cc.on_off_mode.value = "off"
                self._attr_hvac_mode = self._get_hvac_mode()
                self.coordinator.async_update_listeners()
        else:
            _LOGGER.debug(
                "Device '%s' request to turn off ignored because device is already off",
                self._device.name,
            )
