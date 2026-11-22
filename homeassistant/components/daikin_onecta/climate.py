"""Support for the Daikin HVAC."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Literal, cast, override

from daikin_onecta import ClimateControl, ClimateControlClient
from daikin_onecta.models import (
    Characteristic,
    FanDirectionAxis,
    FanDirectionMode,
    FanOperationMode,
    FanSpeedMode,
    Setpoint,
)

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
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
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import CLIMATE_ENTITY_DESCRIPTIONS, FANMODE_FIXED
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    management_point_unique_id,
    present_devices,
)
from .utils import (
    fixed_positions,
    round_temperature_to_step,
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
        for setpoint_type in climate_control.setpoint_types:
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
        # Successful writes update the typed model optimistically so Home
        # Assistant reflects the new state without waiting for the next poll.
        self._attr_native_temperature_unit = self._get_native_temperature_unit()
        self._attr_native_current_temperature = self._get_current_temperature()
        self._attr_max_temp = self._get_max_temp()
        self._attr_min_temp = self._get_min_temp()
        self._attr_target_temperature_step = self._get_target_temperature_step()
        self._attr_native_target_temperature = self._get_target_temperature()
        self._attr_hvac_modes = self._get_hvac_modes()
        self._attr_swing_modes = self._get_swing_modes()
        self._attr_swing_horizontal_modes = self._get_swing_horizontal_modes()
        self._attr_preset_modes = self._get_preset_modes()
        self._attr_fan_modes = self._get_fan_modes()
        self._attr_supported_features = self._get_supported_features()
        self._attr_hvac_mode = self._get_hvac_mode()
        self._attr_swing_mode = self._get_swing_mode()
        self._attr_swing_horizontal_mode = self._get_swing_horizontal_mode()
        self._attr_preset_mode = self._get_preset_mode()
        self._attr_fan_mode = self._get_fan_mode()

    async def _async_execute_climate_command(
        self, command: Callable[[ClimateControlClient], Awaitable[None]]
    ) -> bool:
        """Execute a bound climate command through the serialized gateway."""
        return await self.coordinator.async_execute_command(
            lambda client: command(
                client.climate_control(self._device_id, self._embedded_id)
            )
        )

    async def _async_set_fixed_fan_control(
        self,
        *,
        get_state: Callable[[], FixedFanControlState | None],
        target: int,
        set_mode: Callable[[ClimateControlClient], Awaitable[None]],
        set_position: Callable[[ClimateControlClient, int], Awaitable[None]],
        unavailable_key: str,
    ) -> bool:
        """Select fixed fan mode and its requested speed or louvre position."""
        if (state := get_state()) is None:
            self._raise_service_validation_error(unavailable_key)
        current_mode, fixed = state
        if fixed is None or not fixed.settable:
            self._raise_service_validation_error(unavailable_key)

        if current_mode.value != FANMODE_FIXED:
            if not current_mode.settable:
                self._raise_service_validation_error(unavailable_key)
            if not await self._async_execute_climate_command(set_mode):
                return False
            current_mode.value = FANMODE_FIXED
            # Keep the confirmed mode if the subsequent position write fails.
            self._publish_write_update()

        if fixed.value != target:
            if not await self._async_execute_climate_command(
                lambda climate: set_position(climate, target)
            ):
                return False
            if (state := get_state()) is not None and (fixed := state[1]) is not None:
                fixed.value = target
        return True

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return (
            super().available
            and (climate_control := self._climate_control()) is not None
            and self._setpoint in climate_control.setpoint_types
        )

    def _climate_control(self) -> ClimateControl | None:
        """Return typed native climate-control state from the library."""
        management_point = self._management_point
        return (
            management_point.climate_control if management_point is not None else None
        )

    def _operation_mode(self) -> Characteristic[str] | None:
        """Return the operation-mode characteristic."""
        cc = self._climate_control()
        return cc.operation_mode if cc is not None else None

    def _fan_operation(
        self, operation_mode: str | None = None
    ) -> FanOperationMode | None:
        """Return fan controls for an operation mode."""
        cc = self._climate_control()
        return cc.fan_operation(operation_mode) if cc is not None else None

    def _preset_characteristic(self, daikin_mode: str) -> Characteristic[Any] | None:
        """Return a preset characteristic by Daikin API name."""
        cc = self._climate_control()
        return cc.mode_characteristic(daikin_mode) if cc is not None else None

    def _get_setpoint(self, operation_mode: str | None = None) -> Setpoint | None:
        """Return a setpoint for an operation mode."""
        cc = self._climate_control()
        return cc.setpoint(self._setpoint, operation_mode) if cc is not None else None

    def _get_supported_features(self) -> ClimateEntityFeature:
        """Return the features supported by this climate entity."""
        supported_features = ClimateEntityFeature(0)
        setpointdict = self._get_setpoint()
        if setpointdict is not None and setpointdict.settable:
            supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if self._attr_preset_modes and len(self._attr_preset_modes) > 1:
            supported_features |= ClimateEntityFeature.PRESET_MODE
        cc = self._climate_control()
        if cc is not None:
            if cc.on_off_mode is not None and cc.on_off_mode.settable:
                supported_features |= (
                    ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
                )
            if self._attr_fan_modes:
                supported_features |= ClimateEntityFeature.FAN_MODE
            if self._attr_swing_modes:
                supported_features |= ClimateEntityFeature.SWING_MODE
            if self._attr_swing_horizontal_modes:
                supported_features |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        return supported_features

    def _get_current_temperature(self) -> float | None:
        """Return the current temperature for this setpoint."""
        cc = self._climate_control()
        return cc.current_temperature(self._setpoint) if cc is not None else None

    def _get_native_temperature_unit(self) -> UnitOfTemperature:
        """Return the Daikin temperature unit, defaulting to Celsius."""
        setpoint = self._get_setpoint()
        unit = setpoint.unit if setpoint is not None else None
        if unit is None:
            cc = self._climate_control()
            sensory_target = (
                "leavingWaterTemperature"
                if self._setpoint == "leavingWaterOffset"
                else self._setpoint
            )
            sensory_data = cc.sensory_data(sensory_target) if cc is not None else None
            unit = sensory_data.unit if sensory_data is not None else None
        return temperature_unit_or_celsius(unit)

    def _get_max_temp(self) -> float:
        """Return the maximum configurable temperature."""
        setpointdict = self._get_setpoint()
        return (
            setpointdict.max_value
            if setpointdict is not None and setpointdict.max_value is not None
            else TemperatureConverter.convert(
                DEFAULT_MAX_TEMP,
                UnitOfTemperature.CELSIUS,
                self.native_temperature_unit,
            )
        )

    def _get_min_temp(self) -> float:
        """Return the minimum configurable temperature."""
        setpointdict = self._get_setpoint()
        return (
            setpointdict.min_value
            if setpointdict is not None and setpointdict.min_value is not None
            else TemperatureConverter.convert(
                DEFAULT_MIN_TEMP,
                UnitOfTemperature.CELSIUS,
                self.native_temperature_unit,
            )
        )

    def _get_target_temperature(self) -> float | None:
        """Return the configured target temperature."""
        value: float | None = None
        setpointdict = self._get_setpoint()
        if setpointdict is not None:
            value = setpointdict.value
        return value

    def _get_target_temperature_step(self) -> float | None:
        """Return the target temperature increment."""
        setpoint = self._get_setpoint()
        return setpoint.step_value if setpoint is not None else None

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the HVAC mode and/or target temperature."""
        if ClimateServiceArgument.HVAC_MODE in kwargs:
            await self.async_handle_set_hvac_mode_service(
                kwargs[ClimateServiceArgument.HVAC_MODE]
            )

        if ClimateServiceArgument.TEMPERATURE in kwargs:
            target_temperature = float(kwargs[ClimateServiceArgument.TEMPERATURE])
            # Validate controllability before checking whether rounding is a no-op.
            operationmode = self._operation_mode()
            if operationmode is None:
                self._raise_service_validation_error(
                    "climate_operation_mode_unavailable"
                )
            omv = operationmode.value
            setpoint = self._get_setpoint(omv)
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
                res = await self._async_execute_climate_command(
                    lambda climate: climate.set_temperature(omv, self._setpoint, value)
                )
                # When updating the value to the daikin cloud worked update our local cached version
                if res:
                    setpointdict = self._get_setpoint(omv)
                    if setpointdict is not None:
                        setpointdict.value = value
                        self._publish_write_update()
                else:
                    self._raise_command_failed("set_temperature_failed")

    def _get_hvac_mode(self) -> HVACMode | None:
        """Return current HVAC mode."""
        cc = self._climate_control()
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

    def _get_hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        modes: list[HVACMode] = []
        cc = self._climate_control()
        if cc is not None and cc.on_off_mode is not None and cc.on_off_mode.settable:
            modes.append(HVACMode.OFF)
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
        cc = self._climate_control()
        if (
            cc is not None
            and cc.on_off_mode is not None
            and cc.on_off_mode.value not in {"on", "off"}
        ):
            self._raise_service_validation_error("climate_power_unavailable")

        operation_mode = None
        if hvac_mode != HVACMode.OFF:
            operation_mode = self._native_hvac_mode(hvac_mode)
            if operation_mode is None:
                self._raise_service_validation_error("climate_hvac_mode_unavailable")

        # First determine the new settings for onOffMode/operationMode
        on_off_mode = None
        if hvac_mode == HVACMode.OFF:
            if self.hvac_mode != HVACMode.OFF:
                on_off_mode = "off"
        elif self.hvac_mode == HVACMode.OFF:
            on_off_mode = "on"

        # Only set the on/off to Daikin when we need to change it
        if on_off_mode is not None:
            if cc is None or cc.on_off_mode is None or not cc.on_off_mode.settable:
                self._raise_service_validation_error("climate_power_unavailable")
            if not await self._async_execute_climate_command(
                lambda climate: climate.set_power(on_off_mode == "on")
            ):
                self._raise_command_failed("set_hvac_mode_failed")
            cc = self._climate_control()
            if cc is not None and cc.on_off_mode is not None:
                cc.on_off_mode.value = on_off_mode
                # Publish the confirmed power change before a subsequent
                # operation-mode write, which may be rejected by the cloud.
                self._publish_write_update()

        # Only set the advertised operationMode when it has changed.
        if (
            operation_mode is not None
            and cc is not None
            and cc.operation_mode is not None
            and operation_mode != cc.operation_mode.value
        ):
            if not await self._async_execute_climate_command(
                lambda climate: climate.set_operation_mode(operation_mode)
            ):
                self._raise_command_failed("set_hvac_mode_failed")
            cc = self._climate_control()
            if cc is not None and cc.operation_mode is not None:
                cc.operation_mode.value = operation_mode
            # When switching HVAC mode it could be that we can set min/max/target/etc
            # which we couldn't set with a previous HVAC mode.
            self._publish_write_update()

    def _get_fan_mode(self) -> str | None:
        """Return the active fan mode."""
        fan_operation = self._fan_operation()
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

    def _get_fan_modes(self) -> list[str]:
        """Return available fan modes."""
        fan_operation = self._fan_operation()
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
            else:
                fan_modes.append(mode)
        return fan_modes

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        fan_mode = str(fan_mode)
        fan_operation = self._fan_operation()
        cc = self._climate_control()
        if (
            fan_operation is None
            or fan_operation.fan_speed is None
            or cc is None
            or cc.operation_mode is None
        ):
            self._raise_service_validation_error("fan_control_unavailable")
        if fan_mode not in self._get_fan_modes():
            self._raise_service_validation_error("fan_mode_unavailable")
        fan_speed = fan_operation.fan_speed
        operation_mode = cc.operation_mode.value
        if fan_mode.isnumeric():

            def get_fixed_speed_state() -> FixedFanControlState | None:
                if (
                    fan_operation := self._fan_operation(operation_mode)
                ) is None or fan_operation.fan_speed is None:
                    return None
                fan_speed = fan_operation.fan_speed
                fixed = fan_speed.modes.get(FANMODE_FIXED) if fan_speed.modes else None
                return fan_speed.current_mode, fixed

            if not await self._async_set_fixed_fan_control(
                get_state=get_fixed_speed_state,
                target=int(fan_mode),
                set_mode=lambda climate: climate.set_fan_mode(
                    operation_mode, FANMODE_FIXED
                ),
                set_position=lambda climate, speed: climate.set_fixed_fan_speed(
                    operation_mode, speed
                ),
                unavailable_key="fan_control_unavailable",
            ):
                self._raise_command_failed("set_fan_mode_failed")
        elif fan_speed.current_mode.value != fan_mode:
            if not fan_speed.current_mode.settable:
                self._raise_service_validation_error("fan_control_unavailable")
            if not await self._async_execute_climate_command(
                lambda climate: climate.set_fan_mode(operation_mode, fan_mode)
            ):
                self._raise_command_failed("set_fan_mode_failed")
            fan_operation = self._fan_operation(operation_mode)
            if fan_operation is None or fan_operation.fan_speed is None:
                return
            fan_speed = fan_operation.fan_speed
            fan_speed.current_mode.value = fan_mode

        self._publish_write_update()

    def _get_swing_mode_for_direction(
        self, direction: Literal["vertical", "horizontal"]
    ) -> str | None:
        """Return current swing mode for an axis."""
        axis = self._fan_direction_axis(direction)
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

    def _get_swing_mode(self) -> str | None:
        """Return the vertical swing mode."""
        return self._get_swing_mode_for_direction("vertical")

    def _get_swing_horizontal_mode(self) -> str | None:
        """Return the horizontal swing mode."""
        return self._get_swing_mode_for_direction("horizontal")

    def _get_swing_modes_for_direction(
        self, direction: Literal["vertical", "horizontal"]
    ) -> list[str]:
        """Return supported swing modes for an axis."""
        axis = self._fan_direction_axis(direction)
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
                        axis.current_mode.value == FANMODE_FIXED
                        or axis.current_mode.settable
                    )
                    and positions is not None
                ):
                    swing_modes.extend(str(position) for position in positions)
                    continue
            if axis.current_mode.settable:
                swing_modes.append(_DAIKIN_SWING_TO_HA.get(mode.lower(), mode.lower()))
        return swing_modes

    def _get_swing_modes(self) -> list[str]:
        """Return the supported vertical swing modes."""
        return self._get_swing_modes_for_direction("vertical")

    def _get_swing_horizontal_modes(self) -> list[str]:
        """Return the supported horizontal swing modes."""
        return self._get_swing_modes_for_direction("horizontal")

    def _fan_direction_axis(
        self,
        direction: Literal["vertical", "horizontal"],
        operation_mode: str | None = None,
    ) -> FanDirectionAxis | None:
        """Return one fan-direction axis for the current or given mode."""
        fan_operation = self._fan_operation(operation_mode)
        if fan_operation is None or fan_operation.fan_direction is None:
            return None
        return cast(
            "FanDirectionAxis | None", getattr(fan_operation.fan_direction, direction)
        )

    async def _async_set_swing(
        self, direction: Literal["vertical", "horizontal"], swing_mode: str
    ) -> bool:
        """Set a fan-direction mode."""
        cc = self._climate_control()
        if cc is None or cc.operation_mode is None:
            self._raise_service_validation_error("swing_control_unavailable")
        axis = self._fan_direction_axis(direction)
        if axis is None:
            self._raise_service_validation_error("swing_control_unavailable")
        operation_mode = cc.operation_mode.value

        if swing_mode.isnumeric():

            def get_fixed_direction_state() -> FixedFanControlState | None:
                axis = self._fan_direction_axis(direction, operation_mode)
                if axis is None:
                    return None
                fixed = axis.modes.get(FANMODE_FIXED) if axis.modes else None
                return axis.current_mode, fixed

            return await self._async_set_fixed_fan_control(
                get_state=get_fixed_direction_state,
                target=int(swing_mode),
                set_mode=lambda climate: climate.set_fan_direction(
                    operation_mode, direction, FANMODE_FIXED
                ),
                set_position=lambda climate, position: climate.set_fixed_fan_direction(
                    operation_mode, direction, position
                ),
                unavailable_key="swing_control_unavailable",
            )

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
        result = await self._async_execute_climate_command(
            lambda climate: climate.set_fan_direction(
                operation_mode, direction, new_mode
            )
        )
        if result:
            axis = self._fan_direction_axis(direction, operation_mode)
            if axis is not None:
                axis.current_mode.value = new_mode
        return result

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the vertical swing mode."""
        if swing_mode not in self._get_swing_modes():
            self._raise_service_validation_error("swing_control_unavailable")
        res = True
        if self.swing_mode != swing_mode:
            res = await self._async_set_swing("vertical", swing_mode)

            if res is True:
                self._publish_write_update()
            else:
                self._raise_command_failed("set_swing_mode_failed")

    @override
    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set the horizontal swing mode."""
        if swing_horizontal_mode not in self._get_swing_horizontal_modes():
            self._raise_service_validation_error("swing_control_unavailable")
        res = True
        if self.swing_horizontal_mode != swing_horizontal_mode:
            res = await self._async_set_swing("horizontal", swing_horizontal_mode)

            if res is True:
                self._publish_write_update()
            else:
                self._raise_command_failed("set_swing_mode_failed")

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
            result = await self._async_execute_climate_command(
                lambda climate: climate.set_holiday_mode(False)
            )
        else:
            result = await self._async_execute_climate_command(
                lambda climate: climate.set_mode_characteristic(daikin_mode, False)
            )
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
            result = await self._async_execute_climate_command(
                lambda climate: climate.set_holiday_mode(
                    True,
                    start_date=today,
                    end_date=today + timedelta(days=60),
                )
            )
        else:
            result = await self._async_execute_climate_command(
                lambda climate: climate.set_mode_characteristic(daikin_mode, True)
            )
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
        if preset_mode == self.preset_mode:
            return
        if preset_mode not in self._get_preset_modes():
            self._raise_service_validation_error("preset_mode_unavailable")
        if (current_preset := self.preset_mode) not in (None, PRESET_NONE):
            if not await self._async_disable_preset_mode(current_preset):
                self._raise_command_failed("set_preset_mode_failed")
            self._publish_write_update()

        if preset_mode != PRESET_NONE:
            if not await self._async_enable_preset_mode(preset_mode):
                self._raise_command_failed("set_preset_mode_failed")
            self._publish_write_update()

    def _get_preset_modes(self) -> list[str]:
        """Return supported preset modes."""
        return [
            PRESET_NONE,
            *sorted(
                mode
                for mode in PRESET_MODES
                if (
                    (preset := self._preset_characteristic(HA_PRESET_TO_DAIKIN[mode]))
                    is not None
                    and preset.settable
                )
            ),
        ]

    @override
    async def async_turn_on(self) -> None:
        """Turn device CLIMATE on."""
        cc = self._climate_control()
        if cc is None or cc.on_off_mode is None:
            self._raise_service_validation_error("climate_power_unavailable")
        if cc.on_off_mode.value not in {"on", "off"}:
            self._raise_service_validation_error("climate_power_unavailable")
        if cc.on_off_mode.value == "off":
            if not cc.on_off_mode.settable:
                self._raise_service_validation_error("climate_power_unavailable")
            if not await self._async_execute_climate_command(
                lambda climate: climate.set_power(True)
            ):
                self._raise_command_failed("turn_on_failed")
            else:
                cc = self._climate_control()
                if cc is None or cc.on_off_mode is None:
                    return
                cc.on_off_mode.value = "on"
                self._publish_write_update()

    @override
    async def async_turn_off(self) -> None:
        """Turn the climate entity off."""
        cc = self._climate_control()
        if cc is None or cc.on_off_mode is None:
            self._raise_service_validation_error("climate_power_unavailable")
        if cc.on_off_mode.value not in {"on", "off"}:
            self._raise_service_validation_error("climate_power_unavailable")
        if cc.on_off_mode.value == "on":
            if not cc.on_off_mode.settable:
                self._raise_service_validation_error("climate_power_unavailable")
            if not await self._async_execute_climate_command(
                lambda climate: climate.set_power(False)
            ):
                self._raise_command_failed("turn_off_failed")
            else:
                cc = self._climate_control()
                if cc is None or cc.on_off_mode is None:
                    return
                cc.on_off_mode.value = "off"
                self._publish_write_update()
