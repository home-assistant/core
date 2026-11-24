"""Support for the Daikin HVAC."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Literal, cast, override

from daikin_onecta import ClimateControl, ClimateControlClient
from daikin_onecta.client import OnectaClient
from daikin_onecta.models import (
    Characteristic,
    FanDirectionAxis,
    FanDirectionMode,
    FanOperationMode,
    FanSpeedMode,
    Setpoint,
)

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CLIMATE_ENTITY_DESCRIPTIONS, FANMODE_FIXED, LEAVING_WATER_OFFSET
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    present_devices,
)
from .utils import (
    fixed_positions,
    management_point_unique_id,
    round_temperature_to_step,
    set_optional_temperature_bound,
    temperature_unit_or_celsius,
)

PARALLEL_UPDATES = 1

_DAIKIN_SWING_TO_HA = {"stop": SWING_OFF, "swing": SWING_ON}

PRESET_MODES = (PRESET_BOOST, PRESET_AWAY, PRESET_COMFORT, PRESET_ECO)


DAIKIN_HVAC_TO_HA = {
    "fanOnly": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
    "cooling": HVACMode.COOL,
    "heating": HVACMode.HEAT,
    "heatingDay": HVACMode.HEAT,
    "heatingNight": HVACMode.HEAT,
    "auto": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
}

FixedFanMode = FanDirectionMode | FanSpeedMode
FixedFanControlState = tuple[Characteristic[str], FixedFanMode | None]

HA_PRESET_TO_DAIKIN = {
    PRESET_AWAY: "holidayMode",
    PRESET_NONE: "off",
    PRESET_BOOST: "powerfulMode",
    PRESET_COMFORT: "comfortMode",
    PRESET_ECO: "econoMode",
}


def _has_other_climate_setpoint(climate_control: ClimateControl) -> bool:
    """Return whether the point has a non-offset climate target."""
    return any(
        setpoint_type != LEAVING_WATER_OFFSET
        and setpoint_type in CLIMATE_ENTITY_DESCRIPTIONS
        for setpoint_type in climate_control.setpoint_types
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin climate based on config_entry."""
    coordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: [
            entity
            for device in present_devices(coordinator)
            for entity in _create_climate_entities(device, coordinator, is_known)
        ],
    )


def _create_climate_entities(
    device: DaikinOnectaDevice,
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinClimate]:
    """Create climate entities for each Daikin temperature target.

    A ``climateControl`` management point represents one independently
    controllable Daikin zone. Its ``temperatureControl`` data can advertise
    more than one target type for that zone, such as room temperature, leaving
    water temperature, or leaving-water offset. These target types are control
    strategies, not additional zones, and all share the same management point.
    """
    entities: list[DaikinClimate] = []
    for management_point in device.device.management_points_by_type("climateControl"):
        climate_control = management_point.climate_control
        if climate_control is None:
            continue
        setpoint_types = climate_control.setpoint_types
        has_other_climate_setpoint = _has_other_climate_setpoint(climate_control)
        for setpoint_type in setpoint_types:
            if setpoint_type == LEAVING_WATER_OFFSET and has_other_climate_setpoint:
                continue
            description = CLIMATE_ENTITY_DESCRIPTIONS.get(setpoint_type)
            if description is None:
                continue
            unique_id = management_point_unique_id(
                device.id, management_point.embedded_id, setpoint_type
            )
            if is_known(Platform.CLIMATE, unique_id):
                continue
            entities.append(
                DaikinClimate(
                    device,
                    setpoint_type,
                    coordinator,
                    management_point.embedded_id,
                    description,
                )
            )
    return entities


class DaikinClimate(DaikinManagementPointEntity, ClimateEntity):
    """Representation of one Daikin temperature target in a climate zone."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    # ``setpoint`` is a Daikin target type under
    # temperatureControl/value/operationModes/<mode>/setpoints, for example
    # roomTemperature or leavingWaterOffset. It is not a zone identifier.
    def __init__(
        self,
        device: DaikinOnectaDevice,
        setpoint: str,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        description: ClimateEntityDescription,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(device, coordinator, embedded_id)
        self._setpoint = setpoint
        self._attr_unique_id = management_point_unique_id(
            self._device_id, self._embedded_id, self._setpoint
        )
        self.entity_description = description
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh all state attributes from the device."""
        climate_control = self._climate_control()
        active_presets = self._get_active_preset_modes(climate_control)
        # Successful writes update the typed model optimistically so Home
        # Assistant reflects the new state without waiting for the next poll.
        self._attr_native_temperature_unit = self._get_native_temperature_unit(
            climate_control
        )
        self._attr_native_current_temperature = self._get_current_temperature(
            climate_control
        )
        set_optional_temperature_bound(self, "max", self._get_max_temp(climate_control))
        set_optional_temperature_bound(self, "min", self._get_min_temp(climate_control))
        self._attr_target_temperature_step = self._get_target_temperature_step(
            climate_control
        )
        self._attr_native_target_temperature = self._get_target_temperature(
            climate_control
        )
        hvac_modes = self._get_hvac_modes(climate_control)
        swing_modes = self._get_swing_modes(climate_control)
        swing_horizontal_modes = self._get_swing_horizontal_modes(climate_control)
        preset_modes = self._get_preset_modes(climate_control, active_presets)
        fan_modes = self._get_fan_modes(climate_control)
        self._attr_hvac_modes = hvac_modes
        self._attr_swing_modes = swing_modes
        self._attr_swing_horizontal_modes = swing_horizontal_modes
        self._attr_preset_modes = preset_modes
        self._attr_fan_modes = fan_modes
        self._attr_supported_features = self._get_supported_features(
            climate_control,
            preset_modes=preset_modes,
            fan_modes=fan_modes,
            swing_modes=swing_modes,
            swing_horizontal_modes=swing_horizontal_modes,
        )
        self._attr_hvac_mode = self._get_hvac_mode(climate_control)
        self._attr_swing_mode = self._get_swing_mode(climate_control)
        self._attr_swing_horizontal_mode = self._get_swing_horizontal_mode(
            climate_control
        )
        self._attr_preset_mode = self._get_preset_mode(active_presets)
        self._attr_fan_mode = self._get_fan_mode(climate_control)

    async def _async_set_fixed_fan_control(
        self,
        *,
        get_state: Callable[[], FixedFanControlState | None],
        target: int,
        set_mode: Callable[[ClimateControlClient], Awaitable[None]],
        set_position: Callable[[ClimateControlClient, int], Awaitable[None]],
        unavailable_key: str,
        command_failed_key: str,
    ) -> None:
        """Select fixed fan mode and its requested speed or louvre position."""
        if (state := get_state()) is None:
            self._raise_service_validation_error(unavailable_key)
        current_mode, fixed = state
        if fixed is None:
            self._raise_service_validation_error(unavailable_key)
        if current_mode.value.lower() == FANMODE_FIXED and fixed.value == target:
            return
        if not fixed.settable:
            self._raise_service_validation_error(unavailable_key)

        if current_mode.value.lower() != FANMODE_FIXED:
            if not current_mode.settable:
                self._raise_service_validation_error(unavailable_key)
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control, set_mode, command_failed_key
            )
            if (state := get_state()) is not None:
                state[0].value = FANMODE_FIXED
            # Keep the confirmed mode if the subsequent position write fails.
            self._publish_write_update()

        if (state := get_state()) is None or (fixed := state[1]) is None:
            self._raise_service_validation_error(unavailable_key)
        if fixed.value != target:
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: set_position(climate, target),
                command_failed_key,
            )
            if (state := get_state()) is not None and (fixed := state[1]) is not None:
                fixed.value = target

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return (
            super().available
            and (climate_control := self._climate_control()) is not None
            and self._setpoint in climate_control.setpoint_types
            and not (
                self._setpoint == LEAVING_WATER_OFFSET
                and _has_other_climate_setpoint(climate_control)
            )
        )

    def _climate_control(self) -> ClimateControl | None:
        """Return typed native climate-control state from the library."""
        management_point = self._management_point
        return (
            management_point.climate_control if management_point is not None else None
        )

    async def _async_set_power(self, on: bool, translation_key: str) -> None:
        """Set the climate control's power state when it differs."""
        cc = self._climate_control()
        if cc is None or cc.on_off_mode is None:
            self._raise_service_validation_error("climate_power_unavailable")
        if cc.on_off_mode.value not in {"on", "off"}:
            self._raise_service_validation_error("climate_power_unavailable")
        state = "on" if on else "off"
        if cc.on_off_mode.value == state:
            return
        if not cc.on_off_mode.settable:
            self._raise_service_validation_error("climate_power_unavailable")
        await self._async_execute_sub_client_command(
            OnectaClient.climate_control,
            lambda climate: climate.set_power(on),
            translation_key,
        )
        if (cc := self._climate_control()) is not None and cc.on_off_mode is not None:
            cc.on_off_mode.value = state
            self._publish_write_update()

    def _operation_mode(
        self, climate_control: ClimateControl | None
    ) -> Characteristic[str] | None:
        """Return the operation-mode characteristic."""
        return climate_control.operation_mode if climate_control is not None else None

    def _fan_operation(
        self,
        climate_control: ClimateControl | None,
        operation_mode: str | None = None,
    ) -> FanOperationMode | None:
        """Return fan controls for an operation mode."""
        return (
            climate_control.fan_operation(operation_mode)
            if climate_control is not None
            else None
        )

    def _preset_characteristic(
        self, daikin_mode: str, climate_control: ClimateControl | None
    ) -> Characteristic[Any] | None:
        """Return a preset characteristic by Daikin API name."""
        return (
            climate_control.mode_characteristic(daikin_mode)
            if climate_control is not None
            else None
        )

    def _get_setpoint(
        self,
        climate_control: ClimateControl | None,
        operation_mode: str | None = None,
    ) -> Setpoint | None:
        """Return a setpoint for an operation mode."""
        return (
            climate_control.setpoint(self._setpoint, operation_mode)
            if climate_control is not None
            else None
        )

    def _get_target_setpoint(
        self, climate_control: ClimateControl | None
    ) -> Setpoint | None:
        """Return the setpoint exposed as the climate target temperature."""
        if self._setpoint == LEAVING_WATER_OFFSET:
            return None
        return self._get_setpoint(climate_control)

    def _get_supported_features(
        self,
        climate_control: ClimateControl | None,
        *,
        preset_modes: list[str],
        fan_modes: list[str],
        swing_modes: list[str],
        swing_horizontal_modes: list[str],
    ) -> ClimateEntityFeature:
        """Return the features supported by this climate entity."""
        supported_features = ClimateEntityFeature(0)
        if (
            setpoint := self._get_target_setpoint(climate_control)
        ) is not None and setpoint.settable:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if len(preset_modes) > 1:
            supported_features |= ClimateEntityFeature.PRESET_MODE
        cc = climate_control
        if cc is not None:
            if (
                cc.on_off_mode is not None and cc.on_off_mode.settable
            ) or self._operation_mode_controls_power(cc):
                supported_features |= (
                    ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
                )
            if fan_modes and self._fan_mode_is_settable(cc):
                supported_features |= ClimateEntityFeature.FAN_MODE
            if swing_modes:
                supported_features |= ClimateEntityFeature.SWING_MODE
            if swing_horizontal_modes:
                supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        return supported_features

    def _operation_mode_controls_power(self, climate_control: ClimateControl) -> bool:
        """Return whether operationMode can turn the unit off and back on."""
        operation_mode = self._operation_mode(climate_control)
        if (
            climate_control.on_off_mode is not None
            or operation_mode is None
            or not operation_mode.settable
        ):
            return False
        modes = [DAIKIN_HVAC_TO_HA.get(mode) for mode in operation_mode.values or []]
        return HVACMode.OFF in modes and any(
            mode is not None and mode != HVACMode.OFF for mode in modes
        )

    def _fan_mode_is_settable(self, climate_control: ClimateControl | None) -> bool:
        """Return whether any fan mode control is writable."""
        fan_operation = self._fan_operation(climate_control)
        fan_speed = fan_operation.fan_speed if fan_operation is not None else None
        if fan_speed is None:
            return False
        if fan_speed.current_mode.settable:
            return True
        fixed = (fan_speed.modes or {}).get(FANMODE_FIXED)
        return fixed is not None and fixed.settable

    def _get_current_temperature(
        self, climate_control: ClimateControl | None
    ) -> float | None:
        """Return the current temperature for this setpoint."""
        cc = climate_control
        return cc.current_temperature(self._setpoint) if cc is not None else None

    def _get_native_temperature_unit(
        self, climate_control: ClimateControl | None
    ) -> UnitOfTemperature:
        """Return the Daikin temperature unit, defaulting to Celsius."""
        cc = climate_control
        setpoint = self._get_setpoint(cc)
        unit = setpoint.unit if setpoint is not None else None
        if unit is None:
            sensory_target = (
                "leavingWaterTemperature"
                if self._setpoint == LEAVING_WATER_OFFSET
                else self._setpoint
            )
            sensory_data = cc.sensory_data(sensory_target) if cc is not None else None
            unit = sensory_data.unit if sensory_data is not None else None
        return temperature_unit_or_celsius(unit)

    def _get_max_temp(self, climate_control: ClimateControl | None) -> float | None:
        """Return the maximum configurable temperature, if provided."""
        setpoint = self._get_target_setpoint(climate_control)
        return (
            float(setpoint.max_value)
            if setpoint is not None and setpoint.max_value is not None
            else None
        )

    def _get_min_temp(self, climate_control: ClimateControl | None) -> float | None:
        """Return the minimum configurable temperature, if provided."""
        setpoint = self._get_target_setpoint(climate_control)
        return (
            float(setpoint.min_value)
            if setpoint is not None and setpoint.min_value is not None
            else None
        )

    def _get_target_temperature(
        self, climate_control: ClimateControl | None
    ) -> float | None:
        """Return the configured target temperature."""
        value: float | None = None
        if (setpoint := self._get_target_setpoint(climate_control)) is not None:
            value = setpoint.value
        return value

    def _get_target_temperature_step(
        self, climate_control: ClimateControl | None
    ) -> float | None:
        """Return the target temperature increment."""
        setpoint = self._get_target_setpoint(climate_control)
        return setpoint.step_value if setpoint is not None else None

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the HVAC mode and/or target temperature."""
        hvac_mode = kwargs.get(ClimateServiceArgument.HVAC_MODE)
        # Keep the unit on while applying a setpoint that accompanies a power-off
        # request; some units reject setpoint writes after they have been turned off.
        if hvac_mode is not None and hvac_mode != HVACMode.OFF:
            await self.async_handle_set_hvac_mode_service(hvac_mode)

        if ClimateServiceArgument.TEMPERATURE in kwargs:
            target_temperature = float(kwargs[ClimateServiceArgument.TEMPERATURE])
            # Validate controllability before checking whether rounding is a no-op.
            climate_control = self._climate_control()
            operationmode = self._operation_mode(climate_control)
            if operationmode is None:
                self._raise_service_validation_error(
                    "climate_operation_mode_unavailable"
                )
            omv = operationmode.value
            setpoint = self._get_setpoint(climate_control, omv)
            if setpoint is None or not setpoint.settable:
                self._raise_service_validation_error("climate_temperature_unavailable")

            value = round_temperature_to_step(
                target_temperature,
                setpoint.step_value,
                setpoint.min_value,
                setpoint.max_value,
                fallback_minimum=self.min_temp,
                fallback_maximum=self.max_temp,
            )

            if self._attr_native_target_temperature != value:
                await self._async_execute_sub_client_command(
                    OnectaClient.climate_control,
                    lambda climate: climate.set_temperature(omv, self._setpoint, value),
                    "set_temperature_failed",
                )
                setpointdict = self._get_setpoint(self._climate_control(), omv)
                if setpointdict is not None:
                    setpointdict.value = value
                    self._publish_write_update()

        if hvac_mode == HVACMode.OFF:
            await self.async_handle_set_hvac_mode_service(hvac_mode)

    def _get_hvac_mode(self, climate_control: ClimateControl | None) -> HVACMode | None:
        """Return current HVAC mode."""
        cc = climate_control
        if cc is None:
            return None
        if (onoff := cc.on_off_mode) is not None:
            if onoff.value == "off":
                return HVACMode.OFF
            if onoff.value != "on":
                return None
        operation_mode = cc.operation_mode
        if operation_mode is None or operation_mode.value is None:
            return None
        return DAIKIN_HVAC_TO_HA.get(operation_mode.value)

    def _get_hvac_modes(self, climate_control: ClimateControl | None) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        modes: list[HVACMode] = []
        cc = climate_control
        if (
            cc is not None
            and cc.on_off_mode is not None
            and (cc.on_off_mode.settable or cc.on_off_mode.value == "off")
        ):
            modes.append(HVACMode.OFF)
        operationmode = self._operation_mode(cc)
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

    def _native_hvac_mode(
        self, hvac_mode: HVACMode, climate_control: ClimateControl | None
    ) -> str | None:
        """Return an advertised native mode for a requested HVAC mode."""
        operation_mode = self._operation_mode(climate_control)
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
        cc = self._climate_control()
        if (
            cc is not None
            and cc.on_off_mode is not None
            and cc.on_off_mode.value not in {"on", "off"}
        ):
            self._raise_service_validation_error("climate_power_unavailable")
        if (
            hvac_mode != HVACMode.OFF
            and cc is not None
            and cc.on_off_mode is not None
            and not cc.on_off_mode.settable
            and cc.on_off_mode.value == "off"
        ):
            self._raise_service_validation_error("climate_power_unavailable")

        has_power_control = (
            cc is not None and cc.on_off_mode is not None and cc.on_off_mode.settable
        )
        current_hvac_mode = self.hvac_mode
        operation_mode = None
        if hvac_mode != HVACMode.OFF or (
            not has_power_control and current_hvac_mode != HVACMode.OFF
        ):
            operation_mode = self._native_hvac_mode(hvac_mode, cc)
            if operation_mode is None:
                self._raise_service_validation_error("climate_hvac_mode_unavailable")

        # First determine the new settings for onOffMode/operationMode
        on_off_mode = None
        if has_power_control and hvac_mode == HVACMode.OFF:
            if current_hvac_mode != HVACMode.OFF:
                on_off_mode = "off"
        elif has_power_control and current_hvac_mode == HVACMode.OFF:
            on_off_mode = "on"

        # Only set the on/off to Daikin when we need to change it
        if on_off_mode is not None:
            if cc is None or cc.on_off_mode is None:
                self._raise_service_validation_error("climate_power_unavailable")
            await self._async_set_power(on_off_mode == "on", "set_hvac_mode_failed")
            cc = self._climate_control()

        # Only set the advertised operationMode when it has changed.
        if (
            operation_mode is not None
            and cc is not None
            and cc.operation_mode is not None
            and operation_mode != cc.operation_mode.value
        ):
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: climate.set_operation_mode(operation_mode),
                "set_hvac_mode_failed",
            )
            cc = self._climate_control()
            if cc is not None and cc.operation_mode is not None:
                cc.operation_mode.value = operation_mode
            # When switching HVAC mode it could be that we can set min/max/target/etc
            # which we couldn't set with a previous HVAC mode.
            self._publish_write_update()

    def _get_fan_mode(self, climate_control: ClimateControl | None) -> str | None:
        """Return the active fan mode."""
        fan_operation = self._fan_operation(climate_control)
        if fan_operation is None or fan_operation.fan_speed is None:
            return None
        fan_speed = fan_operation.fan_speed
        mode = cast("str | None", fan_speed.current_mode.value)
        if mode is None:
            return None
        if (
            mode == FANMODE_FIXED
            and fan_speed.modes
            and FANMODE_FIXED in fan_speed.modes
        ):
            if (
                fixed_speed := cast(
                    "str | int | None", fan_speed.modes[FANMODE_FIXED].value
                )
            ) is None:
                return None
            mode = str(fixed_speed)
        return mode

    def _get_fan_modes(self, climate_control: ClimateControl | None) -> list[str]:
        """Return available fan modes."""
        fan_operation = self._fan_operation(climate_control)
        if fan_operation is None or fan_operation.fan_speed is None:
            return []
        fan_speed = fan_operation.fan_speed
        fan_modes: list[str] = []
        modes = fan_speed.current_mode.values or []
        if not fan_speed.current_mode.settable:
            modes = (
                [FANMODE_FIXED] if fan_speed.current_mode.value == FANMODE_FIXED else []
            )
        for mode in modes:
            if (
                mode == FANMODE_FIXED
                and fan_speed.modes
                and FANMODE_FIXED in fan_speed.modes
            ):
                fixed = fan_speed.modes[FANMODE_FIXED]
                positions = fixed_positions(fixed) if fixed.settable else None
                if positions is not None:
                    fan_modes.extend(str(position) for position in positions)
                elif (
                    fan_speed.current_mode.value == FANMODE_FIXED
                    and fixed.value is not None
                ):
                    fan_modes.append(str(fixed.value))
            else:
                fan_modes.append(mode)
        return fan_modes

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        fan_mode = str(fan_mode)
        cc = self._climate_control()
        fan_operation = self._fan_operation(cc)
        if (
            fan_operation is None
            or fan_operation.fan_speed is None
            or cc is None
            or cc.operation_mode is None
        ):
            self._raise_service_validation_error("fan_control_unavailable")
        if fan_mode not in self._get_fan_modes(cc):
            self._raise_service_validation_error("fan_mode_unavailable")
        fan_speed = fan_operation.fan_speed
        operation_mode = cc.operation_mode.value
        if fan_mode.isnumeric():

            def get_fixed_speed_state() -> FixedFanControlState | None:
                if (
                    fan_operation := self._fan_operation(
                        self._climate_control(), operation_mode
                    )
                ) is None or fan_operation.fan_speed is None:
                    return None
                fan_speed = fan_operation.fan_speed
                fixed = fan_speed.modes.get(FANMODE_FIXED) if fan_speed.modes else None
                return fan_speed.current_mode, fixed

            await self._async_set_fixed_fan_control(
                get_state=get_fixed_speed_state,
                target=int(fan_mode),
                set_mode=lambda climate: climate.set_fan_mode(
                    operation_mode, FANMODE_FIXED
                ),
                set_position=lambda climate, speed: climate.set_fixed_fan_speed(
                    operation_mode, speed
                ),
                unavailable_key="fan_control_unavailable",
                command_failed_key="set_fan_mode_failed",
            )
        elif fan_speed.current_mode.value != fan_mode:
            if not fan_speed.current_mode.settable:
                self._raise_service_validation_error("fan_control_unavailable")
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: climate.set_fan_mode(operation_mode, fan_mode),
                "set_fan_mode_failed",
            )
            fan_operation = self._fan_operation(self._climate_control(), operation_mode)
            if fan_operation is None or fan_operation.fan_speed is None:
                return
            fan_speed = fan_operation.fan_speed
            fan_speed.current_mode.value = fan_mode

        self._publish_write_update()

    def _get_swing_mode_for_direction(
        self,
        direction: Literal["vertical", "horizontal"],
        climate_control: ClimateControl | None,
    ) -> str | None:
        """Return current swing mode for an axis."""
        axis = self._fan_direction_axis(climate_control, direction)
        if axis is None:
            return None
        if (value := cast("str | None", axis.current_mode.value)) is None:
            return None
        mode = value.lower()
        if mode == FANMODE_FIXED:
            swing_modes = (
                self._attr_swing_modes
                if direction == "vertical"
                else self._attr_swing_horizontal_modes
            ) or []
            fixed = axis.modes.get(FANMODE_FIXED) if axis.modes else None
            if fixed is not None:
                position = str(fixed.value)
                if position in swing_modes:
                    return position
            return mode if mode in swing_modes else None
        return _DAIKIN_SWING_TO_HA.get(mode, mode)

    def _get_swing_mode(self, climate_control: ClimateControl | None) -> str | None:
        """Return the vertical swing mode."""
        return self._get_swing_mode_for_direction("vertical", climate_control)

    def _get_swing_horizontal_mode(
        self, climate_control: ClimateControl | None
    ) -> str | None:
        """Return the horizontal swing mode."""
        return self._get_swing_mode_for_direction("horizontal", climate_control)

    def _get_swing_modes_for_direction(
        self,
        direction: Literal["vertical", "horizontal"],
        climate_control: ClimateControl | None,
    ) -> list[str]:
        """Return supported swing modes for an axis."""
        axis = self._fan_direction_axis(climate_control, direction)
        if axis is None:
            return []
        # Daikin also exposes comfort and floor-heating airflow direction modes.
        swing_modes: list[str] = []
        for mode in axis.current_mode.values or []:
            if mode.lower() == FANMODE_FIXED:
                fixed = axis.modes.get(FANMODE_FIXED) if axis.modes else None
                positions = fixed_positions(fixed) if fixed is not None else None
                if (
                    fixed is not None
                    and fixed.settable
                    and (
                        axis.current_mode.value.lower() == FANMODE_FIXED
                        or axis.current_mode.settable
                    )
                    and positions is not None
                ):
                    swing_modes.extend(str(position) for position in positions)
                    continue
            if axis.current_mode.settable:
                swing_modes.append(_DAIKIN_SWING_TO_HA.get(mode.lower(), mode.lower()))
        return swing_modes

    def _get_swing_modes(self, climate_control: ClimateControl | None) -> list[str]:
        """Return the supported vertical swing modes."""
        return self._get_swing_modes_for_direction("vertical", climate_control)

    def _get_swing_horizontal_modes(
        self, climate_control: ClimateControl | None
    ) -> list[str]:
        """Return the supported horizontal swing modes."""
        return self._get_swing_modes_for_direction("horizontal", climate_control)

    def _fan_direction_axis(
        self,
        climate_control: ClimateControl | None,
        direction: Literal["vertical", "horizontal"],
        operation_mode: str | None = None,
    ) -> FanDirectionAxis | None:
        """Return one fan-direction axis for the current or given mode."""
        fan_operation = self._fan_operation(climate_control, operation_mode)
        if fan_operation is None or fan_operation.fan_direction is None:
            return None
        return cast(
            "FanDirectionAxis | None", getattr(fan_operation.fan_direction, direction)
        )

    async def _async_set_swing(
        self, direction: Literal["vertical", "horizontal"], swing_mode: str
    ) -> None:
        """Set a fan-direction mode."""
        cc = self._climate_control()
        if cc is None or cc.operation_mode is None:
            self._raise_service_validation_error("swing_control_unavailable")
        axis = self._fan_direction_axis(cc, direction)
        if axis is None:
            self._raise_service_validation_error("swing_control_unavailable")
        operation_mode = cc.operation_mode.value

        if swing_mode.isnumeric():

            def get_fixed_direction_state() -> FixedFanControlState | None:
                axis = self._fan_direction_axis(
                    self._climate_control(), direction, operation_mode
                )
                if axis is None:
                    return None
                fixed = axis.modes.get(FANMODE_FIXED) if axis.modes else None
                return axis.current_mode, fixed

            await self._async_set_fixed_fan_control(
                get_state=get_fixed_direction_state,
                target=int(swing_mode),
                set_mode=lambda climate: climate.set_fan_direction(
                    operation_mode, direction, FANMODE_FIXED
                ),
                set_position=lambda climate, position: climate.set_fixed_fan_direction(
                    operation_mode, direction, position
                ),
                unavailable_key="swing_control_unavailable",
                command_failed_key="set_swing_mode_failed",
            )
            return

        if not axis.current_mode.settable:
            self._raise_service_validation_error("swing_control_unavailable")

        new_mode = next(
            (
                mode
                for mode in axis.current_mode.values or []
                if swing_mode == _DAIKIN_SWING_TO_HA.get(mode.lower(), mode.lower())
            ),
            None,
        )
        if new_mode is None:
            self._raise_service_validation_error("swing_control_unavailable")
        await self._async_execute_sub_client_command(
            OnectaClient.climate_control,
            lambda climate: climate.set_fan_direction(
                operation_mode, direction, new_mode
            ),
            "set_swing_mode_failed",
        )
        axis = self._fan_direction_axis(
            self._climate_control(), direction, operation_mode
        )
        if axis is not None:
            axis.current_mode.value = new_mode

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode."""
        if swing_mode not in self._get_swing_modes(self._climate_control()):
            self._raise_service_validation_error("swing_control_unavailable")
        if self.swing_mode != swing_mode:
            await self._async_set_swing("vertical", swing_mode)
            self._publish_write_update()

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the horizontal swing mode."""
        if swing_horizontal_mode not in self._get_swing_horizontal_modes(
            self._climate_control()
        ):
            self._raise_service_validation_error("swing_control_unavailable")
        if self.swing_horizontal_mode != swing_horizontal_mode:
            await self._async_set_swing("horizontal", swing_horizontal_mode)
            self._publish_write_update()

    def _get_preset_mode(self, active_modes: list[str]) -> str:
        """Return the active preset mode."""
        return next(iter(active_modes), PRESET_NONE)

    def _get_active_preset_modes(
        self, climate_control: ClimateControl | None
    ) -> list[str]:
        """Return every preset reported as active by Daikin."""
        active_modes = []
        for mode in PRESET_MODES:
            preset = self._preset_characteristic(
                HA_PRESET_TO_DAIKIN[mode], climate_control
            )
            if preset is None:
                continue
            if mode == PRESET_AWAY:
                if preset.value.enabled:
                    active_modes.append(mode)
            elif preset.value == "on":
                active_modes.append(mode)
        return active_modes

    async def _async_disable_preset_mode(self, preset_mode: str) -> None:
        """Disable the current Daikin preset mode."""
        daikin_mode = HA_PRESET_TO_DAIKIN[preset_mode]
        if preset_mode == PRESET_AWAY:
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: climate.set_holiday_mode(False),
                "set_preset_mode_failed",
            )
        else:
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: climate.set_mode_characteristic(daikin_mode, False),
                "set_preset_mode_failed",
            )
        preset = self._preset_characteristic(daikin_mode, self._climate_control())
        if preset_mode == PRESET_AWAY and preset is not None:
            preset.value.enabled = False
        elif preset is not None:
            preset.value = "off"

    async def _async_enable_preset_mode(self, preset_mode: str) -> None:
        """Enable the requested Daikin preset mode."""
        daikin_mode = HA_PRESET_TO_DAIKIN[preset_mode]
        if self.hvac_mode == HVACMode.OFF and preset_mode == PRESET_BOOST:
            await self.async_turn_on()
            if self.hvac_mode == HVACMode.OFF:
                self._raise_command_failed("set_preset_mode_failed")
        if preset_mode == PRESET_AWAY:
            today = dt_util.now().date()
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: climate.set_holiday_mode(
                    True,
                    start_date=today,
                    end_date=today + timedelta(days=60),
                ),
                "set_preset_mode_failed",
            )
        else:
            await self._async_execute_sub_client_command(
                OnectaClient.climate_control,
                lambda climate: climate.set_mode_characteristic(daikin_mode, True),
                "set_preset_mode_failed",
            )
        preset = self._preset_characteristic(daikin_mode, self._climate_control())
        if preset_mode == PRESET_AWAY and preset is not None:
            preset.value.enabled = True
        elif preset is not None:
            preset.value = "on"

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the active preset mode."""
        climate_control = self._climate_control()
        active_presets = self._get_active_preset_modes(climate_control)
        if preset_mode not in self._get_preset_modes(climate_control, active_presets):
            self._raise_service_validation_error("preset_mode_unavailable")
        if preset_mode == self.preset_mode:
            return

        presets_to_disable = []
        for current_preset in active_presets:
            if current_preset == preset_mode:
                continue
            preset = self._preset_characteristic(
                HA_PRESET_TO_DAIKIN[current_preset], climate_control
            )
            if preset is None:
                self._raise_service_validation_error("preset_mode_unavailable")
            if not preset.settable:
                self._raise_service_validation_error("preset_mode_unavailable")
            presets_to_disable.append(current_preset)
        for current_preset in presets_to_disable:
            await self._async_disable_preset_mode(current_preset)
            self._publish_write_update()

        if preset_mode != PRESET_NONE and preset_mode not in active_presets:
            await self._async_enable_preset_mode(preset_mode)
            self._publish_write_update()

    def _get_preset_modes(
        self,
        climate_control: ClimateControl | None,
        active_modes: list[str],
    ) -> list[str]:
        """Return supported preset modes."""
        return [
            PRESET_NONE,
            *sorted(
                mode
                for mode in PRESET_MODES
                if mode in active_modes
                or (
                    (
                        preset := self._preset_characteristic(
                            HA_PRESET_TO_DAIKIN[mode], climate_control
                        )
                    )
                    is not None
                    and preset.settable
                )
            ),
        ]

    @override
    async def async_turn_on(self) -> None:
        """Turn device CLIMATE on."""
        cc = self._climate_control()
        if cc is not None and cc.on_off_mode is None:
            if self.hvac_mode == HVACMode.OFF:
                next_mode = next(
                    (mode for mode in self.hvac_modes if mode != HVACMode.OFF), None
                )
                if next_mode is None:
                    self._raise_service_validation_error(
                        "climate_hvac_mode_unavailable"
                    )
                await self.async_set_hvac_mode(next_mode)
            return
        await self._async_set_power(True, "turn_on_failed")

    @override
    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        cc = self._climate_control()
        if cc is not None and cc.on_off_mode is None:
            await self.async_set_hvac_mode(HVACMode.OFF)
            return
        await self._async_set_power(False, "turn_off_failed")
