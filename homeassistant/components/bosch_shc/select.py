"""Platform for select integration."""

from __future__ import annotations

import logging

from boschshcpy import (
    SHCSession,
    SHCShutterContact2Plus,
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
from boschshcpy.device import SHCDevice

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SESSION, DOMAIN
from .entity import SHCEntity, device_excluded

LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Motion sensitivity: exclude UNKNOWN from user-visible options.
_MOTION_SENSITIVITY_OPTIONS = [
    PirSensorConfigurationService.MotionSensitivity.HIGH.name,
    PirSensorConfigurationService.MotionSensitivity.MIDDLE.name,
    PirSensorConfigurationService.MotionSensitivity.LOW.name,
]

# Vibration sensitivity: all values are valid user choices (no UNKNOWN).
_VIBRATION_SENSITIVITY_OPTIONS = [
    VibrationSensorService.SensitivityState.VERY_HIGH.name,
    VibrationSensorService.SensitivityState.HIGH.name,
    VibrationSensorService.SensitivityState.MEDIUM.name,
    VibrationSensorService.SensitivityState.LOW.name,
    VibrationSensorService.SensitivityState.VERY_LOW.name,
]

# Orientation-light response time (PollControl longPollInterval): LONG = lower
# battery use / slower, SHORT = more responsive / higher battery use. Exclude
# UNKNOWN from user-visible options.
_POLL_CONTROL_OPTIONS = [
    PollControlService.PollControlState.LONG.name,
    PollControlService.PollControlState.SHORT.name,
]

# State after power outage: OFF / ON / LAST_STATE (exclude UNKNOWN).
_STATE_AFTER_POWER_OUTAGE_OPTIONS = [
    PowerSwitchConfigurationService.StateAfterPowerOutage.OFF.name,
    PowerSwitchConfigurationService.StateAfterPowerOutage.ON.name,
    PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE.name,
]

# Smoke sensitivity: HIGH / MIDDLE / LOW (exclude UNKNOWN).
_SMOKE_SENSITIVITY_OPTIONS = [
    SmokeSensitivityService.SmokeSensitivityLevel.HIGH.name,
    SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE.name,
    SmokeSensitivityService.SmokeSensitivityLevel.LOW.name,
]

# Display direction: NORMAL / REVERSED (exclude UNKNOWN).
_DISPLAY_DIRECTION_OPTIONS = [
    DisplayDirection.Direction.NORMAL.name,
    DisplayDirection.Direction.REVERSED.name,
]

# Displayed temperature: SETPOINT / MEASURED (exclude UNKNOWN).
_DISPLAYED_TEMPERATURE_OPTIONS = [
    DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT.name,
    DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED.name,
]

# Terminal type: all user-selectable values (exclude UNKNOWN).
_TERMINAL_TYPE_OPTIONS = [
    TerminalConfiguration.Type.NOT_CONNECTED.name,
    TerminalConfiguration.Type.FLOOR_SENSOR_CONNECTED.name,
    TerminalConfiguration.Type.FLOOR_SENSOR_USED_FOR_REGULATION.name,
    TerminalConfiguration.Type.FLOOR_SENSOR_DISPLAYED.name,
    TerminalConfiguration.Type.FLOOR_SENSOR_DISPLAYED_AND_USED_FOR_REGULATION.name,
    TerminalConfiguration.Type.VOLT_FREE_SENSOR_CONNECTED.name,
    TerminalConfiguration.Type.VOLT_FREE_SENSOR_CONNECTED_AND_USED_FOR_OPERATION.name,
    TerminalConfiguration.Type.OUTDOOR_SENSOR_CONNECTED.name,
]

# WallThermostatConfiguration valve type: exclude UNKNOWN.
_VALVE_TYPE_OPTIONS = [
    WallThermostatConfiguration.ValveType.NORMALLY_CLOSE.name,
    WallThermostatConfiguration.ValveType.NORMALLY_OPEN.name,
]

# WallThermostatConfiguration heater type: exclude UNKNOWN.
_HEATER_TYPE_OPTIONS = [
    WallThermostatConfiguration.HeaterType.FLOOR_HEATING.name,
    WallThermostatConfiguration.HeaterType.FLOOR_HEATING_LOW_ENERGY.name,
    WallThermostatConfiguration.HeaterType.RADIATOR.name,
    WallThermostatConfiguration.HeaterType.CONVECTOR_PASSIVE.name,
    WallThermostatConfiguration.HeaterType.CONVECTOR_ACTIVE.name,
]

# SwitchConfiguration switch type: exclude UNKNOWN.
_SWITCH_TYPE_OPTIONS = [
    SwitchConfiguration.SwitchType.NONE.name,
    SwitchConfiguration.SwitchType.PUSHBUTTON.name,
    SwitchConfiguration.SwitchType.SWITCH.name,
    SwitchConfiguration.SwitchType.NO_SWITCH.name,
]

# SwitchConfiguration actuator type: exclude UNKNOWN.
_ACTUATOR_TYPE_OPTIONS = [
    SwitchConfiguration.ActuatorType.NORMALLY_CLOSED.name,
    SwitchConfiguration.ActuatorType.NORMALLY_OPEN.name,
    SwitchConfiguration.ActuatorType.UNSUPPORTED.name,
]

# SwitchConfiguration output mode: exclude UNKNOWN.
_OUTPUT_MODE_OPTIONS = [
    SwitchConfiguration.OutputMode.ATTACHED.name,
    SwitchConfiguration.OutputMode.DETACHED.name,
    SwitchConfiguration.OutputMode.DETACHED_SHORT_PRESS.name,
    SwitchConfiguration.OutputMode.DETACHED_LONG_PRESS.name,
    SwitchConfiguration.OutputMode.UNSUPPORTED.name,
]

# SmartSensitivity manual level: HIGH / MIDDLE / LOW (exclude UNKNOWN).
_SMART_SENSITIVITY_OPTIONS = [
    SmartSensitivityControlService.MotionSensitivity.HIGH.name,
    SmartSensitivityControlService.MotionSensitivity.MIDDLE.name,
    SmartSensitivityControlService.MotionSensitivity.LOW.name,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC select platform."""
    entities: list[SelectEntity] = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for device in session.device_helper.motion_detectors2:
        if device_excluded(device, config_entry.options):
            continue
        if not hasattr(device, "motion_sensitivity"):
            continue
        try:
            # Probe the accessor — raises AttributeError when the service is absent.
            _ = device.motion_sensitivity
        except AttributeError:
            continue
        entities.append(
            MotionSensitivitySelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )

    for device in session.device_helper.shutter_contacts2:
        if device_excluded(device, config_entry.options):
            continue
        if not isinstance(device, SHCShutterContact2Plus):
            continue
        entities.append(
            VibrationSensitivitySelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )

    # PowerSwitchConfiguration: state after power outage (smart plugs).
    for device in (
        getattr(session.device_helper, "smart_plugs", [])
        + getattr(session.device_helper, "smart_plugs_compact", [])
    ):
        if device_excluded(device, config_entry.options):
            continue
        if not getattr(device, "supports_power_switch_configuration", False):
            continue
        if getattr(device, "state_after_power_outage", None) is None:
            continue
        entities.append(
            StateAfterPowerOutageSelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )

    # SmokeSensitivity: level select for smoke detectors and twinguards.
    for device in (
        getattr(session.device_helper, "smoke_detectors", [])
        + getattr(session.device_helper, "twinguards", [])
    ):
        if device_excluded(device, config_entry.options):
            continue
        if not getattr(device, "supports_smoke_sensitivity", False):
            continue
        if getattr(device, "smoke_sensitivity", None) is None:
            continue
        entities.append(
            SmokeSensitivitySelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )

    # DisplayDirection select (ThermostatGen2 / RoomThermostat2).
    for device in (
        getattr(session.device_helper, "thermostats", [])
        + getattr(session.device_helper, "roomthermostats", [])
    ):
        if device_excluded(device, config_entry.options):
            continue
        if (
            getattr(device, "supports_display_direction", False)
            and getattr(device, "display_direction", None) is not None
        ):
            entities.append(
                DisplayDirectionSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            getattr(device, "supports_displayed_temperature", False)
            and getattr(device, "displayed_temperature", None) is not None
        ):
            entities.append(
                DisplayedTemperatureSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )
        # WallThermostatConfiguration: valve + heater type (ThermostatGen2 only).
        if (
            getattr(device, "supports_wall_thermostat_configuration", False)
            and getattr(device, "valve_type", None) is not None
        ):
            entities.append(
                ValveTypeSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            getattr(device, "supports_wall_thermostat_configuration", False)
            and getattr(device, "heater_type", None) is not None
        ):
            entities.append(
                HeaterTypeSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )
        # TerminalConfiguration type (RoomThermostat2 only).
        if (
            getattr(device, "supports_terminal_configuration", False)
            and getattr(device, "terminal_type", None) is not None
        ):
            entities.append(
                TerminalTypeSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )

    # SwitchConfiguration selects (MicromoduleRelay + LightControl).
    for device in (
        getattr(session.device_helper, "micromodule_relays", [])
        + getattr(session.device_helper, "micromodule_light_controls", [])
    ):
        if device_excluded(device, config_entry.options):
            continue
        if (
            getattr(device, "supports_switch_configuration", False)
            and getattr(device, "switch_type", None) is not None
        ):
            entities.append(
                SwitchTypeSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            getattr(device, "supports_switch_configuration", False)
            and getattr(device, "actuator_type", None) is not None
        ):
            entities.append(
                ActuatorTypeSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            getattr(device, "supports_switch_configuration", False)
            and getattr(device, "output_mode", None) is not None
        ):
            entities.append(
                OutputModeSelect(
                    device=device,
                    entry_id=config_entry.entry_id,
                )
            )

    # SmartSensitivityControl manual level selects (Motion Detector II).
    # Two entities: one for SECURITY context, one for COMFORT context.
    for device in getattr(session.device_helper, "motion_detectors2", []):
        if device_excluded(device, config_entry.options):
            continue
        if not getattr(device, "supports_smart_sensitivity", False):
            continue
        if getattr(device, "get_smart_sensitivity", None) is None:
            continue
        entities.append(
            SmartSensitivitySecurityLevelSelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )
        entities.append(
            SmartSensitivityComfortLevelSelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )

    # Orientation-light response time (PollControl) for Motion Detector II.
    for device in getattr(session.device_helper, "motion_detectors2", []):
        if device_excluded(device, config_entry.options):
            continue
        if getattr(device, "long_poll_interval", None) is None:
            continue
        entities.append(
            OrientationLightResponseSelect(
                device=device,
                entry_id=config_entry.entry_id,
            )
        )

    if entities:
        async_add_entities(entities)


class MotionSensitivitySelect(SHCEntity, SelectEntity):
    """Select entity for Motion Detector II [+M] motion sensitivity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _MOTION_SENSITIVITY_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the motion sensitivity select entity."""
        super().__init__(device, entry_id)
        self._attr_name = "Motion Sensitivity"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_motion_sensitivity"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current sensitivity option."""
        try:
            return self._device.motion_sensitivity.name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown motion_sensitivity for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the motion sensitivity."""
        MotionSensitivity = PirSensorConfigurationService.MotionSensitivity
        await self._device.async_set_motion_sensitivity(MotionSensitivity[option])


class OrientationLightResponseSelect(SHCEntity, SelectEntity):
    """Select for the Motion Detector II orientation-light response time.

    Backed by the PollControl service (longPollInterval): LONG = lower battery
    consumption / slower response, SHORT = faster response / higher battery use.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-cog-outline"
    _attr_options = _POLL_CONTROL_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the orientation-light response-time select entity."""
        super().__init__(device, entry_id)
        self._attr_name = "Orientation Light Response Time"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_orientation_light_response"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current poll-interval option."""
        try:
            val = self._device.long_poll_interval
            if val is None or val.name not in self._attr_options:
                return None
            return val.name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown long_poll_interval for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the orientation-light response time (poll interval)."""
        state = PollControlService.PollControlState[option]
        await self._device.async_set_long_poll_interval(state)


class VibrationSensitivitySelect(SHCEntity, SelectEntity):
    """Select entity for ShutterContact2Plus vibration sensitivity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _VIBRATION_SENSITIVITY_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the vibration sensitivity select entity."""
        super().__init__(device, entry_id)
        self._attr_name = "Vibration Sensitivity"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_vibration_sensitivity"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current sensitivity option."""
        try:
            return self._device.sensitivity.name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown vibration sensitivity for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the vibration sensitivity."""
        SensitivityState = VibrationSensorService.SensitivityState
        await self._device.async_set_sensitivity(SensitivityState[option])


class StateAfterPowerOutageSelect(SHCEntity, SelectEntity):
    """Select entity for smart plug power-loss behaviour."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _STATE_AFTER_POWER_OUTAGE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the state-after-power-outage select."""
        super().__init__(device, entry_id)
        self._attr_name = "State After Power Outage"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_state_after_power_outage"
        )

    @property
    def current_option(self) -> str | None:
        """Return current option name, None if unknown."""
        try:
            val = self._device.state_after_power_outage
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown state_after_power_outage for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the state-after-power-outage."""
        StateAfterPowerOutage = PowerSwitchConfigurationService.StateAfterPowerOutage
        await self._device.async_set_state_after_power_outage(StateAfterPowerOutage[option])


class SmokeSensitivitySelect(SHCEntity, SelectEntity):
    """Select entity for smoke detector / twinguard smoke sensitivity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SMOKE_SENSITIVITY_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the smoke sensitivity select."""
        super().__init__(device, entry_id)
        self._attr_name = "Smoke Sensitivity"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_smoke_sensitivity"
        )

    @property
    def current_option(self) -> str | None:
        """Return current sensitivity level name."""
        try:
            val = self._device.smoke_sensitivity
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown smoke_sensitivity for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the smoke sensitivity level."""
        SmokeSensitivityLevel = SmokeSensitivityService.SmokeSensitivityLevel
        await self._device.async_set_smoke_sensitivity(SmokeSensitivityLevel[option])


class DisplayDirectionSelect(SHCEntity, SelectEntity):
    """Select entity for thermostat display orientation."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _DISPLAY_DIRECTION_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the display direction select."""
        super().__init__(device, entry_id)
        self._attr_name = "Display Direction"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_display_direction"
        )

    @property
    def current_option(self) -> str | None:
        """Return current direction."""
        try:
            val = self._device.display_direction
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown display_direction for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the display direction."""
        Direction = DisplayDirection.Direction
        await self._device.async_set_display_direction(Direction[option])


class DisplayedTemperatureSelect(SHCEntity, SelectEntity):
    """Select entity for which temperature value the thermostat display shows."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _DISPLAYED_TEMPERATURE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the displayed-temperature select."""
        super().__init__(device, entry_id)
        self._attr_name = "Displayed Temperature"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_displayed_temperature"
        )

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        try:
            val = self._device.displayed_temperature
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown displayed_temperature for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the displayed-temperature type."""
        DisplayedTemperature = DisplayedTemperatureConfiguration.DisplayedTemperature
        await self._device.async_set_displayed_temperature(DisplayedTemperature[option])


class TerminalTypeSelect(SHCEntity, SelectEntity):
    """Select entity for RoomThermostat2 terminal (external sensor) type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _TERMINAL_TYPE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the terminal type select."""
        super().__init__(device, entry_id)
        self._attr_name = "Terminal Type"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_terminal_type"
        )

    @property
    def current_option(self) -> str | None:
        """Return current terminal type."""
        try:
            val = self._device.terminal_type
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown terminal_type for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the terminal type."""
        Type = TerminalConfiguration.Type
        await self._device.async_set_terminal_type(Type[option])


class ValveTypeSelect(SHCEntity, SelectEntity):
    """Select entity for ThermostatGen2 valve type (normally open/close)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _VALVE_TYPE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the valve type select."""
        super().__init__(device, entry_id)
        self._attr_name = "Valve Type"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_valve_type"
        )

    @property
    def current_option(self) -> str | None:
        """Return current valve type."""
        try:
            val = self._device.valve_type
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown valve_type for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the valve type."""
        ValveType = WallThermostatConfiguration.ValveType
        await self._device.async_set_valve_type(ValveType[option])


class HeaterTypeSelect(SHCEntity, SelectEntity):
    """Select entity for ThermostatGen2 heater type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _HEATER_TYPE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the heater type select."""
        super().__init__(device, entry_id)
        self._attr_name = "Heater Type"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_heater_type"
        )

    @property
    def current_option(self) -> str | None:
        """Return current heater type."""
        try:
            val = self._device.heater_type
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown heater_type for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the heater type."""
        HeaterType = WallThermostatConfiguration.HeaterType
        await self._device.async_set_heater_type(HeaterType[option])


class SwitchTypeSelect(SHCEntity, SelectEntity):
    """Select entity for SwitchConfiguration switch type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SWITCH_TYPE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the switch type select."""
        super().__init__(device, entry_id)
        self._attr_name = "Switch Type"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_switch_type"
        )

    @property
    def current_option(self) -> str | None:
        """Return current switch type."""
        try:
            val = self._device.switch_type
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown switch_type for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the switch type."""
        SwitchType = SwitchConfiguration.SwitchType
        await self._device.async_set_switch_type(SwitchType[option])


class ActuatorTypeSelect(SHCEntity, SelectEntity):
    """Select entity for SwitchConfiguration actuator type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _ACTUATOR_TYPE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the actuator type select."""
        super().__init__(device, entry_id)
        self._attr_name = "Actuator Type"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_actuator_type"
        )

    @property
    def current_option(self) -> str | None:
        """Return current actuator type."""
        try:
            val = self._device.actuator_type
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown actuator_type for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the actuator type."""
        ActuatorType = SwitchConfiguration.ActuatorType
        await self._device.async_set_actuator_type(ActuatorType[option])


class OutputModeSelect(SHCEntity, SelectEntity):
    """Select entity for SwitchConfiguration output mode."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _OUTPUT_MODE_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the output mode select."""
        super().__init__(device, entry_id)
        self._attr_name = "Output Mode"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_output_mode"
        )

    @property
    def current_option(self) -> str | None:
        """Return current output mode."""
        try:
            val = self._device.output_mode
            if val is None:
                return None
            name = val.name
            if name not in self._attr_options:
                return None
            return name
        except (AttributeError, ValueError) as err:
            LOGGER.warning(
                "Unknown output_mode for %s: %s", self._device.name, err
            )
            return None

    async def async_select_option(self, option: str) -> None:
        """Set the output mode."""
        OutputMode = SwitchConfiguration.OutputMode
        await self._device.async_set_output_mode(OutputMode[option])


class SmartSensitivitySecurityLevelSelect(SHCEntity, SelectEntity):
    """Select entity for SmartSensitivityControl manual level — SECURITY context.

    The MD2 SmartSensitivityControl service stores a per-context manualLevel
    as a MotionSensitivity enum (HIGH/MIDDLE/LOW).  Only created when
    get_smart_sensitivity is available on the device.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SMART_SENSITIVITY_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the security sensitivity level select."""
        super().__init__(device, entry_id)
        self._attr_name = "Smart Sensitivity Security Level"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_smart_sensitivity_security"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current manual level for the SECURITY context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
        sensitivity = self._device.get_smart_sensitivity(ctx)
        if sensitivity is None:
            return None
        level = sensitivity.get("manualLevel")
        if level is None:
            return None
        # level may be an enum or a string
        name = level.name if hasattr(level, "name") else str(level)
        if name not in self._attr_options:
            return None
        return name

    async def async_select_option(self, option: str) -> None:
        """Set the manual level for the SECURITY context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
        level = SmartSensitivityControlService.MotionSensitivity[option]
        await self._device.async_set_smart_sensitivity_manual_level(ctx, level)


class SmartSensitivityComfortLevelSelect(SHCEntity, SelectEntity):
    """Select entity for SmartSensitivityControl manual level — COMFORT context."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SMART_SENSITIVITY_OPTIONS

    def __init__(self, device: SHCDevice, entry_id: str) -> None:
        """Initialize the comfort sensitivity level select."""
        super().__init__(device, entry_id)
        self._attr_name = "Smart Sensitivity Comfort Level"
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}_smart_sensitivity_comfort"
        )

    @property
    def current_option(self) -> str | None:
        """Return the current manual level for the COMFORT context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.COMFORT
        sensitivity = self._device.get_smart_sensitivity(ctx)
        if sensitivity is None:
            return None
        level = sensitivity.get("manualLevel")
        if level is None:
            return None
        # level may be an enum or a string
        name = level.name if hasattr(level, "name") else str(level)
        if name not in self._attr_options:
            return None
        return name

    async def async_select_option(self, option: str) -> None:
        """Set the manual level for the COMFORT context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.COMFORT
        level = SmartSensitivityControlService.MotionSensitivity[option]
        await self._device.async_set_smart_sensitivity_manual_level(ctx, level)
