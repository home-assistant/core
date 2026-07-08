"""Platform for select integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import override

from boschshcpy import SHCShutterContact2Plus
from boschshcpy.device import SHCDevice
from boschshcpy.models_impl import (
    SHCMotionDetector2,
    SHCRoomThermostat2,
    SHCThermostatGen2,
)
from boschshcpy.services_impl import (
    DisplayDirection,
    DisplayedTemperatureConfiguration,
    PirSensorConfigurationService,
    PollControlService,
    PowerSwitchConfigurationService,
    SmartSensitivityControlService,
    SmokeSensitivityService,
    SwitchConfiguration,
    TerminalConfiguration,
    VibrationSensorService,
    WallThermostatConfiguration,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1


def _attr_value_fn(attr: str) -> Callable[[SHCDevice], str | None]:
    """Return a value_fn reading an enum-valued device attribute by name.

    The option is lower-cased so it matches HA's snake_case option/state
    convention and can be looked up in strings.json's entity state translations.
    """

    def _value_fn(device: SHCDevice) -> str | None:
        value = getattr(device, attr)
        return value.name.lower() if value is not None else None

    return _value_fn


def _attr_set_fn(attr: str, enum_cls: type[Enum]) -> Callable[[SHCDevice, str], None]:
    """Return a set_fn writing an enum member (looked up by option name) by attr name."""

    def _set_fn(device: SHCDevice, option: str) -> None:
        setattr(device, attr, enum_cls[option.upper()])

    return _set_fn


def _get_smart_sensitivity(
    device: SHCMotionDetector2,
    context: SmartSensitivityControlService.SmartSensitivityContext,
) -> str | None:
    sensitivity = device.get_smart_sensitivity(context)
    if sensitivity is None:
        return None
    level = sensitivity.get("manualLevel")
    if level is None:
        return None
    return level.name.lower() if hasattr(level, "name") else str(level)


def _set_smart_sensitivity(
    device: SHCMotionDetector2,
    context: SmartSensitivityControlService.SmartSensitivityContext,
    option: str,
) -> None:
    level = SmartSensitivityControlService.MotionSensitivity[option.upper()]
    device.set_smart_sensitivity_manual_level(context, level)


@dataclass(frozen=True, kw_only=True)
class SHCSelectEntityDescription(SelectEntityDescription):
    """Describes a SHC select entity."""

    value_fn: Callable[[SHCDevice], str | None]
    set_fn: Callable[[SHCDevice, str], None]


MOTION_SENSITIVITY_SELECT = "motion_sensitivity"
ORIENTATION_LIGHT_RESPONSE_SELECT = "orientation_light_response"
SMART_SENSITIVITY_SECURITY_SELECT = "smart_sensitivity_security"
SMART_SENSITIVITY_COMFORT_SELECT = "smart_sensitivity_comfort"
VIBRATION_SENSITIVITY_SELECT = "vibration_sensitivity"
STATE_AFTER_POWER_OUTAGE_SELECT = "state_after_power_outage"
SMOKE_SENSITIVITY_SELECT = "smoke_sensitivity"
DISPLAY_DIRECTION_SELECT = "display_direction"
DISPLAYED_TEMPERATURE_SELECT = "displayed_temperature"
VALVE_TYPE_SELECT = "valve_type"
HEATER_TYPE_SELECT = "heater_type"
TERMINAL_TYPE_SELECT = "terminal_type"
SWITCH_TYPE_SELECT = "switch_type"
ACTUATOR_TYPE_SELECT = "actuator_type"
OUTPUT_MODE_SELECT = "output_mode"

SELECT_DESCRIPTIONS: dict[str, SHCSelectEntityDescription] = {
    MOTION_SENSITIVITY_SELECT: SHCSelectEntityDescription(
        key=MOTION_SENSITIVITY_SELECT,
        translation_key=MOTION_SENSITIVITY_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            PirSensorConfigurationService.MotionSensitivity.HIGH.name.lower(),
            PirSensorConfigurationService.MotionSensitivity.MIDDLE.name.lower(),
            PirSensorConfigurationService.MotionSensitivity.LOW.name.lower(),
        ],
        value_fn=_attr_value_fn("motion_sensitivity"),
        set_fn=_attr_set_fn(
            "motion_sensitivity", PirSensorConfigurationService.MotionSensitivity
        ),
    ),
    ORIENTATION_LIGHT_RESPONSE_SELECT: SHCSelectEntityDescription(
        key=ORIENTATION_LIGHT_RESPONSE_SELECT,
        translation_key=ORIENTATION_LIGHT_RESPONSE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            PollControlService.PollControlState.LONG.name.lower(),
            PollControlService.PollControlState.SHORT.name.lower(),
        ],
        value_fn=_attr_value_fn("long_poll_interval"),
        set_fn=_attr_set_fn("long_poll_interval", PollControlService.PollControlState),
    ),
    SMART_SENSITIVITY_SECURITY_SELECT: SHCSelectEntityDescription(
        key=SMART_SENSITIVITY_SECURITY_SELECT,
        translation_key=SMART_SENSITIVITY_SECURITY_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            SmartSensitivityControlService.MotionSensitivity.HIGH.name.lower(),
            SmartSensitivityControlService.MotionSensitivity.MIDDLE.name.lower(),
            SmartSensitivityControlService.MotionSensitivity.LOW.name.lower(),
        ],
        value_fn=lambda device: _get_smart_sensitivity(
            device, SmartSensitivityControlService.SmartSensitivityContext.SECURITY
        ),
        set_fn=lambda device, option: _set_smart_sensitivity(
            device,
            SmartSensitivityControlService.SmartSensitivityContext.SECURITY,
            option,
        ),
    ),
    SMART_SENSITIVITY_COMFORT_SELECT: SHCSelectEntityDescription(
        key=SMART_SENSITIVITY_COMFORT_SELECT,
        translation_key=SMART_SENSITIVITY_COMFORT_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            SmartSensitivityControlService.MotionSensitivity.HIGH.name.lower(),
            SmartSensitivityControlService.MotionSensitivity.MIDDLE.name.lower(),
            SmartSensitivityControlService.MotionSensitivity.LOW.name.lower(),
        ],
        value_fn=lambda device: _get_smart_sensitivity(
            device, SmartSensitivityControlService.SmartSensitivityContext.COMFORT
        ),
        set_fn=lambda device, option: _set_smart_sensitivity(
            device,
            SmartSensitivityControlService.SmartSensitivityContext.COMFORT,
            option,
        ),
    ),
    VIBRATION_SENSITIVITY_SELECT: SHCSelectEntityDescription(
        key=VIBRATION_SENSITIVITY_SELECT,
        translation_key=VIBRATION_SENSITIVITY_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            VibrationSensorService.SensitivityState.VERY_HIGH.name.lower(),
            VibrationSensorService.SensitivityState.HIGH.name.lower(),
            VibrationSensorService.SensitivityState.MEDIUM.name.lower(),
            VibrationSensorService.SensitivityState.LOW.name.lower(),
            VibrationSensorService.SensitivityState.VERY_LOW.name.lower(),
        ],
        value_fn=_attr_value_fn("sensitivity"),
        set_fn=_attr_set_fn("sensitivity", VibrationSensorService.SensitivityState),
    ),
    STATE_AFTER_POWER_OUTAGE_SELECT: SHCSelectEntityDescription(
        key=STATE_AFTER_POWER_OUTAGE_SELECT,
        translation_key=STATE_AFTER_POWER_OUTAGE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            PowerSwitchConfigurationService.StateAfterPowerOutage.OFF.name.lower(),
            PowerSwitchConfigurationService.StateAfterPowerOutage.ON.name.lower(),
            PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE.name.lower(),
        ],
        value_fn=_attr_value_fn("state_after_power_outage"),
        set_fn=_attr_set_fn(
            "state_after_power_outage",
            PowerSwitchConfigurationService.StateAfterPowerOutage,
        ),
    ),
    SMOKE_SENSITIVITY_SELECT: SHCSelectEntityDescription(
        key=SMOKE_SENSITIVITY_SELECT,
        translation_key=SMOKE_SENSITIVITY_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            SmokeSensitivityService.SmokeSensitivityLevel.HIGH.name.lower(),
            SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE.name.lower(),
            SmokeSensitivityService.SmokeSensitivityLevel.LOW.name.lower(),
        ],
        value_fn=_attr_value_fn("smoke_sensitivity"),
        set_fn=_attr_set_fn(
            "smoke_sensitivity", SmokeSensitivityService.SmokeSensitivityLevel
        ),
    ),
    DISPLAY_DIRECTION_SELECT: SHCSelectEntityDescription(
        key=DISPLAY_DIRECTION_SELECT,
        translation_key=DISPLAY_DIRECTION_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            DisplayDirection.Direction.NORMAL.name.lower(),
            DisplayDirection.Direction.REVERSED.name.lower(),
        ],
        value_fn=_attr_value_fn("display_direction"),
        set_fn=_attr_set_fn("display_direction", DisplayDirection.Direction),
    ),
    DISPLAYED_TEMPERATURE_SELECT: SHCSelectEntityDescription(
        key=DISPLAYED_TEMPERATURE_SELECT,
        translation_key=DISPLAYED_TEMPERATURE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT.name.lower(),
            DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED.name.lower(),
        ],
        value_fn=_attr_value_fn("displayed_temperature"),
        set_fn=_attr_set_fn(
            "displayed_temperature",
            DisplayedTemperatureConfiguration.DisplayedTemperature,
        ),
    ),
    VALVE_TYPE_SELECT: SHCSelectEntityDescription(
        key=VALVE_TYPE_SELECT,
        translation_key=VALVE_TYPE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            WallThermostatConfiguration.ValveType.NORMALLY_CLOSE.name.lower(),
            WallThermostatConfiguration.ValveType.NORMALLY_OPEN.name.lower(),
        ],
        value_fn=_attr_value_fn("valve_type"),
        set_fn=_attr_set_fn("valve_type", WallThermostatConfiguration.ValveType),
    ),
    HEATER_TYPE_SELECT: SHCSelectEntityDescription(
        key=HEATER_TYPE_SELECT,
        translation_key=HEATER_TYPE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            WallThermostatConfiguration.HeaterType.FLOOR_HEATING.name.lower(),
            WallThermostatConfiguration.HeaterType.FLOOR_HEATING_LOW_ENERGY.name.lower(),
            WallThermostatConfiguration.HeaterType.RADIATOR.name.lower(),
            WallThermostatConfiguration.HeaterType.CONVECTOR_PASSIVE.name.lower(),
            WallThermostatConfiguration.HeaterType.CONVECTOR_ACTIVE.name.lower(),
        ],
        value_fn=_attr_value_fn("heater_type"),
        set_fn=_attr_set_fn("heater_type", WallThermostatConfiguration.HeaterType),
    ),
    TERMINAL_TYPE_SELECT: SHCSelectEntityDescription(
        key=TERMINAL_TYPE_SELECT,
        translation_key=TERMINAL_TYPE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            TerminalConfiguration.Type.NOT_CONNECTED.name.lower(),
            TerminalConfiguration.Type.FLOOR_SENSOR_CONNECTED.name.lower(),
            TerminalConfiguration.Type.FLOOR_SENSOR_USED_FOR_REGULATION.name.lower(),
            TerminalConfiguration.Type.FLOOR_SENSOR_DISPLAYED.name.lower(),
            TerminalConfiguration.Type.FLOOR_SENSOR_DISPLAYED_AND_USED_FOR_REGULATION.name.lower(),
            TerminalConfiguration.Type.VOLT_FREE_SENSOR_CONNECTED.name.lower(),
            TerminalConfiguration.Type.VOLT_FREE_SENSOR_CONNECTED_AND_USED_FOR_OPERATION.name.lower(),
            TerminalConfiguration.Type.OUTDOOR_SENSOR_CONNECTED.name.lower(),
        ],
        value_fn=_attr_value_fn("terminal_type"),
        set_fn=_attr_set_fn("terminal_type", TerminalConfiguration.Type),
    ),
    SWITCH_TYPE_SELECT: SHCSelectEntityDescription(
        key=SWITCH_TYPE_SELECT,
        translation_key=SWITCH_TYPE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            SwitchConfiguration.SwitchType.NONE.name.lower(),
            SwitchConfiguration.SwitchType.PUSHBUTTON.name.lower(),
            SwitchConfiguration.SwitchType.SWITCH.name.lower(),
            SwitchConfiguration.SwitchType.NO_SWITCH.name.lower(),
        ],
        value_fn=_attr_value_fn("switch_type"),
        set_fn=_attr_set_fn("switch_type", SwitchConfiguration.SwitchType),
    ),
    ACTUATOR_TYPE_SELECT: SHCSelectEntityDescription(
        key=ACTUATOR_TYPE_SELECT,
        translation_key=ACTUATOR_TYPE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            SwitchConfiguration.ActuatorType.NORMALLY_CLOSED.name.lower(),
            SwitchConfiguration.ActuatorType.NORMALLY_OPEN.name.lower(),
            SwitchConfiguration.ActuatorType.UNSUPPORTED.name.lower(),
        ],
        value_fn=_attr_value_fn("actuator_type"),
        set_fn=_attr_set_fn("actuator_type", SwitchConfiguration.ActuatorType),
    ),
    OUTPUT_MODE_SELECT: SHCSelectEntityDescription(
        key=OUTPUT_MODE_SELECT,
        translation_key=OUTPUT_MODE_SELECT,
        entity_category=EntityCategory.CONFIG,
        options=[
            SwitchConfiguration.OutputMode.ATTACHED.name.lower(),
            SwitchConfiguration.OutputMode.DETACHED.name.lower(),
            SwitchConfiguration.OutputMode.DETACHED_SHORT_PRESS.name.lower(),
            SwitchConfiguration.OutputMode.DETACHED_LONG_PRESS.name.lower(),
            SwitchConfiguration.OutputMode.UNSUPPORTED.name.lower(),
        ],
        value_fn=_attr_value_fn("output_mode"),
        set_fn=_attr_set_fn("output_mode", SwitchConfiguration.OutputMode),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC select platform."""
    session = config_entry.runtime_data
    parent_id = session.information.unique_id
    entities: list[SelectEntity] = []

    def _make(device: SHCDevice, select_type: str) -> SHCSelect:
        return SHCSelect(
            device=device,
            entity_description=SELECT_DESCRIPTIONS[select_type],
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )

    for device in session.device_helper.motion_detectors2:
        if device.motion_sensitivity is not None:
            entities.append(_make(device, MOTION_SENSITIVITY_SELECT))
        if device.long_poll_interval is not None:
            entities.append(_make(device, ORIENTATION_LIGHT_RESPONSE_SELECT))
        if (
            device.supports_smart_sensitivity
            and device.get_smart_sensitivity(
                SmartSensitivityControlService.SmartSensitivityContext.SECURITY
            )
            is not None
        ):
            entities.append(_make(device, SMART_SENSITIVITY_SECURITY_SELECT))
            entities.append(_make(device, SMART_SENSITIVITY_COMFORT_SELECT))

    entities.extend(
        _make(device, VIBRATION_SENSITIVITY_SELECT)
        for device in session.device_helper.shutter_contacts2
        if isinstance(device, SHCShutterContact2Plus)
    )

    entities.extend(
        _make(device, STATE_AFTER_POWER_OUTAGE_SELECT)
        for device in (
            *session.device_helper.smart_plugs,
            *session.device_helper.smart_plugs_compact,
        )
        if device.supports_power_switch_configuration
        and device.state_after_power_outage is not None
    )

    entities.extend(
        _make(device, SMOKE_SENSITIVITY_SELECT)
        for device in (
            *session.device_helper.smoke_detectors,
            *session.device_helper.twinguards,
        )
        if device.supports_smoke_sensitivity and device.smoke_sensitivity is not None
    )

    for device in (
        *session.device_helper.thermostats,
        *session.device_helper.roomthermostats,
    ):
        # Gen1 SHCThermostat (model "TRV") has none of the display/wall-config
        # properties below; only SHCThermostatGen2 and SHCRoomThermostat2 do.
        if isinstance(device, (SHCThermostatGen2, SHCRoomThermostat2)):
            if (
                device.supports_display_direction
                and device.display_direction is not None
            ):
                entities.append(_make(device, DISPLAY_DIRECTION_SELECT))
            if (
                device.supports_displayed_temperature
                and device.displayed_temperature is not None
            ):
                entities.append(_make(device, DISPLAYED_TEMPERATURE_SELECT))
        # valve/heater type are only on SHCThermostatGen2 — not on Gen1, and
        # not on SHCRoomThermostat2 either (which has terminal_type instead).
        if isinstance(device, SHCThermostatGen2):
            if (
                device.supports_wall_thermostat_configuration
                and device.valve_type is not None
            ):
                entities.append(_make(device, VALVE_TYPE_SELECT))
            if (
                device.supports_wall_thermostat_configuration
                and device.heater_type is not None
            ):
                entities.append(_make(device, HEATER_TYPE_SELECT))
        if isinstance(device, SHCRoomThermostat2) and (
            device.supports_terminal_configuration and device.terminal_type is not None
        ):
            entities.append(_make(device, TERMINAL_TYPE_SELECT))

    # supports_switch_configuration only exists on SHCMicromoduleRelay (and is
    # there simply "the switch-config service is present"); SHCLightControl
    # has no such flag at all, but its switch_type/actuator_type/output_mode
    # are already null-safe, so checking them directly covers both classes
    # without needing a per-class guard.
    for device in (
        *session.device_helper.micromodule_relays,
        *session.device_helper.micromodule_light_controls,
    ):
        if device.switch_type is not None:
            entities.append(_make(device, SWITCH_TYPE_SELECT))
        if device.actuator_type is not None:
            entities.append(_make(device, ACTUATOR_TYPE_SELECT))
        if device.output_mode is not None:
            entities.append(_make(device, OUTPUT_MODE_SELECT))

    async_add_entities(entities)


class SHCSelect(SHCEntity, SelectEntity):
    """Representation of a SHC select entity."""

    entity_description: SHCSelectEntityDescription

    def __init__(
        self,
        device: SHCDevice,
        entity_description: SHCSelectEntityDescription,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(device, parent_id, entry_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.serial}_{entity_description.key}"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.entity_description.value_fn(self._device)

    @override
    def select_option(self, option: str) -> None:
        """Set the option."""
        self.entity_description.set_fn(self._device, option)
