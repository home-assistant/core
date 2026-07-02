"""Platform for select integration."""

from typing import override

from boschshcpy import SHCShutterContact2Plus, SHCSmokeDetector, SHCTwinguard
from boschshcpy.device import SHCDevice
from boschshcpy.models_impl import (
    SHCLightControl,
    SHCMicromoduleRelay,
    SHCMotionDetector2,
    SHCRoomThermostat2,
    SHCThermostat,
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

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1

_MOTION_SENSITIVITY_OPTIONS = [
    PirSensorConfigurationService.MotionSensitivity.HIGH.name,
    PirSensorConfigurationService.MotionSensitivity.MIDDLE.name,
    PirSensorConfigurationService.MotionSensitivity.LOW.name,
]

_VIBRATION_SENSITIVITY_OPTIONS = [
    VibrationSensorService.SensitivityState.VERY_HIGH.name,
    VibrationSensorService.SensitivityState.HIGH.name,
    VibrationSensorService.SensitivityState.MEDIUM.name,
    VibrationSensorService.SensitivityState.LOW.name,
    VibrationSensorService.SensitivityState.VERY_LOW.name,
]

_POLL_CONTROL_OPTIONS = [
    PollControlService.PollControlState.LONG.name,
    PollControlService.PollControlState.SHORT.name,
]

_STATE_AFTER_POWER_OUTAGE_OPTIONS = [
    PowerSwitchConfigurationService.StateAfterPowerOutage.OFF.name,
    PowerSwitchConfigurationService.StateAfterPowerOutage.ON.name,
    PowerSwitchConfigurationService.StateAfterPowerOutage.LAST_STATE.name,
]

_SMOKE_SENSITIVITY_OPTIONS = [
    SmokeSensitivityService.SmokeSensitivityLevel.HIGH.name,
    SmokeSensitivityService.SmokeSensitivityLevel.MIDDLE.name,
    SmokeSensitivityService.SmokeSensitivityLevel.LOW.name,
]

_DISPLAY_DIRECTION_OPTIONS = [
    DisplayDirection.Direction.NORMAL.name,
    DisplayDirection.Direction.REVERSED.name,
]

_DISPLAYED_TEMPERATURE_OPTIONS = [
    DisplayedTemperatureConfiguration.DisplayedTemperature.SETPOINT.name,
    DisplayedTemperatureConfiguration.DisplayedTemperature.MEASURED.name,
]

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

_VALVE_TYPE_OPTIONS = [
    WallThermostatConfiguration.ValveType.NORMALLY_CLOSE.name,
    WallThermostatConfiguration.ValveType.NORMALLY_OPEN.name,
]

_HEATER_TYPE_OPTIONS = [
    WallThermostatConfiguration.HeaterType.FLOOR_HEATING.name,
    WallThermostatConfiguration.HeaterType.FLOOR_HEATING_LOW_ENERGY.name,
    WallThermostatConfiguration.HeaterType.RADIATOR.name,
    WallThermostatConfiguration.HeaterType.CONVECTOR_PASSIVE.name,
    WallThermostatConfiguration.HeaterType.CONVECTOR_ACTIVE.name,
]

_SWITCH_TYPE_OPTIONS = [
    SwitchConfiguration.SwitchType.NONE.name,
    SwitchConfiguration.SwitchType.PUSHBUTTON.name,
    SwitchConfiguration.SwitchType.SWITCH.name,
    SwitchConfiguration.SwitchType.NO_SWITCH.name,
]

_ACTUATOR_TYPE_OPTIONS = [
    SwitchConfiguration.ActuatorType.NORMALLY_CLOSED.name,
    SwitchConfiguration.ActuatorType.NORMALLY_OPEN.name,
    SwitchConfiguration.ActuatorType.UNSUPPORTED.name,
]

_OUTPUT_MODE_OPTIONS = [
    SwitchConfiguration.OutputMode.ATTACHED.name,
    SwitchConfiguration.OutputMode.DETACHED.name,
    SwitchConfiguration.OutputMode.DETACHED_SHORT_PRESS.name,
    SwitchConfiguration.OutputMode.DETACHED_LONG_PRESS.name,
    SwitchConfiguration.OutputMode.UNSUPPORTED.name,
]

_SMART_SENSITIVITY_OPTIONS = [
    SmartSensitivityControlService.MotionSensitivity.HIGH.name,
    SmartSensitivityControlService.MotionSensitivity.MIDDLE.name,
    SmartSensitivityControlService.MotionSensitivity.LOW.name,
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC select platform."""
    session = config_entry.runtime_data
    parent_id = session.information.unique_id
    entities: list[SelectEntity] = []

    for device in session.device_helper.motion_detectors2:
        if device.motion_sensitivity is not None:
            entities.append(
                SHCMotionSensitivitySelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if device.long_poll_interval is not None:
            entities.append(
                SHCOrientationLightResponseSelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            device.supports_smart_sensitivity
            and device.get_smart_sensitivity(
                SmartSensitivityControlService.SmartSensitivityContext.SECURITY
            )
            is not None
        ):
            entities.extend(
                [
                    SHCSmartSensitivitySecuritySelect(
                        device=device,
                        parent_id=parent_id,
                        entry_id=config_entry.entry_id,
                    ),
                    SHCSmartSensitivityComfortSelect(
                        device=device,
                        parent_id=parent_id,
                        entry_id=config_entry.entry_id,
                    ),
                ]
            )

    entities.extend(
        SHCVibrationSensitivitySelect(
            device=device,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.shutter_contacts2
        if isinstance(device, SHCShutterContact2Plus)
    )

    entities.extend(
        SHCStateAfterPowerOutageSelect(
            device=device,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
        for device in (
            *session.device_helper.smart_plugs,
            *session.device_helper.smart_plugs_compact,
        )
        if device.supports_power_switch_configuration
        and device.state_after_power_outage is not None
    )

    entities.extend(
        SHCSmokeSensitivitySelect(
            device=device,
            parent_id=parent_id,
            entry_id=config_entry.entry_id,
        )
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
        if device.supports_display_direction and device.display_direction is not None:
            entities.append(
                SHCDisplayDirectionSelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            device.supports_displayed_temperature
            and device.displayed_temperature is not None
        ):
            entities.append(
                SHCDisplayedTemperatureSelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            device.supports_wall_thermostat_configuration
            and device.valve_type is not None
        ):
            entities.append(
                SHCValveTypeSelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if (
            device.supports_wall_thermostat_configuration
            and device.heater_type is not None
        ):
            entities.append(
                SHCHeaterTypeSelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )
        if isinstance(device, SHCRoomThermostat2) and (
            device.supports_terminal_configuration and device.terminal_type is not None
        ):
            entities.append(
                SHCTerminalTypeSelect(
                    device=device,
                    parent_id=parent_id,
                    entry_id=config_entry.entry_id,
                )
            )

    for device in (
        *session.device_helper.micromodule_relays,
        *session.device_helper.micromodule_light_controls,
    ):
        if device.supports_switch_configuration:
            if device.switch_type is not None:
                entities.append(
                    SHCSwitchTypeSelect(
                        device=device,
                        parent_id=parent_id,
                        entry_id=config_entry.entry_id,
                    )
                )
            if device.actuator_type is not None:
                entities.append(
                    SHCActuatorTypeSelect(
                        device=device,
                        parent_id=parent_id,
                        entry_id=config_entry.entry_id,
                    )
                )
            if device.output_mode is not None:
                entities.append(
                    SHCOutputModeSelect(
                        device=device,
                        parent_id=parent_id,
                        entry_id=config_entry.entry_id,
                    )
                )

    async_add_entities(entities)


class SHCMotionSensitivitySelect(SHCEntity, SelectEntity):
    """Select entity for Motion Detector II motion sensitivity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _MOTION_SENSITIVITY_OPTIONS
    _attr_translation_key = "motion_sensitivity"

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the motion sensitivity select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_motion_sensitivity"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current sensitivity option."""
        val = self._device.motion_sensitivity
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the motion sensitivity."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "motion_sensitivity",
            PirSensorConfigurationService.MotionSensitivity[option],
        )


class SHCOrientationLightResponseSelect(SHCEntity, SelectEntity):
    """Select entity for Motion Detector II orientation-light response time.

    Backed by the PollControl service (longPollInterval): LONG = lower battery
    consumption / slower response, SHORT = faster response / higher battery use.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-cog-outline"
    _attr_options = _POLL_CONTROL_OPTIONS
    _attr_translation_key = "orientation_light_response"

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the orientation-light response-time select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_orientation_light_response"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current poll-interval option."""
        val = self._device.long_poll_interval
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the orientation-light response time."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "long_poll_interval",
            PollControlService.PollControlState[option],
        )


class SHCSmartSensitivitySecuritySelect(SHCEntity, SelectEntity):
    """Select entity for Motion Detector II smart sensitivity — security context."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SMART_SENSITIVITY_OPTIONS
    _attr_translation_key = "smart_sensitivity_security"

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the smart sensitivity security select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_smart_sensitivity_security"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current manual level for the security context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
        sensitivity = self._device.get_smart_sensitivity(ctx)
        if sensitivity is None:
            return None
        level = sensitivity.get("manualLevel")
        if level is None:
            return None
        name = level.name if hasattr(level, "name") else str(level)
        return name if name in self._attr_options else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the manual level for the security context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.SECURITY
        level = SmartSensitivityControlService.MotionSensitivity[option]
        await self.hass.async_add_executor_job(
            self._device.set_smart_sensitivity_manual_level, ctx, level
        )


class SHCSmartSensitivityComfortSelect(SHCEntity, SelectEntity):
    """Select entity for Motion Detector II smart sensitivity — comfort context."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SMART_SENSITIVITY_OPTIONS
    _attr_translation_key = "smart_sensitivity_comfort"

    def __init__(
        self,
        device: SHCMotionDetector2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the smart sensitivity comfort select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_smart_sensitivity_comfort"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current manual level for the comfort context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.COMFORT
        sensitivity = self._device.get_smart_sensitivity(ctx)
        if sensitivity is None:
            return None
        level = sensitivity.get("manualLevel")
        if level is None:
            return None
        name = level.name if hasattr(level, "name") else str(level)
        return name if name in self._attr_options else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the manual level for the comfort context."""
        ctx = SmartSensitivityControlService.SmartSensitivityContext.COMFORT
        level = SmartSensitivityControlService.MotionSensitivity[option]
        await self.hass.async_add_executor_job(
            self._device.set_smart_sensitivity_manual_level, ctx, level
        )


class SHCVibrationSensitivitySelect(SHCEntity, SelectEntity):
    """Select entity for Shutter Contact 2 Plus vibration sensitivity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _VIBRATION_SENSITIVITY_OPTIONS
    _attr_translation_key = "vibration_sensitivity"

    def __init__(
        self,
        device: SHCShutterContact2Plus,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the vibration sensitivity select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_vibration_sensitivity"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current vibration sensitivity option."""
        val = self._device.sensitivity
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the vibration sensitivity."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "sensitivity",
            VibrationSensorService.SensitivityState[option],
        )


class SHCStateAfterPowerOutageSelect(SHCEntity, SelectEntity):
    """Select entity for smart plug power-loss behaviour."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _STATE_AFTER_POWER_OUTAGE_OPTIONS
    _attr_translation_key = "state_after_power_outage"

    def __init__(
        self,
        device: SHCDevice,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the state-after-power-outage select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_state_after_power_outage"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current power-outage behaviour option."""
        val = self._device.state_after_power_outage
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the state-after-power-outage behaviour."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "state_after_power_outage",
            PowerSwitchConfigurationService.StateAfterPowerOutage[option],
        )


class SHCSmokeSensitivitySelect(SHCEntity, SelectEntity):
    """Select entity for smoke detector / Twinguard smoke sensitivity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SMOKE_SENSITIVITY_OPTIONS
    _attr_translation_key = "smoke_sensitivity"

    def __init__(
        self,
        device: SHCSmokeDetector | SHCTwinguard,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the smoke sensitivity select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_smoke_sensitivity"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current smoke sensitivity level."""
        val = self._device.smoke_sensitivity
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the smoke sensitivity level."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "smoke_sensitivity",
            SmokeSensitivityService.SmokeSensitivityLevel[option],
        )


class SHCDisplayDirectionSelect(SHCEntity, SelectEntity):
    """Select entity for thermostat display orientation."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _DISPLAY_DIRECTION_OPTIONS
    _attr_translation_key = "display_direction"

    def __init__(
        self,
        device: SHCThermostat | SHCRoomThermostat2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the display direction select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_display_direction"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current display direction."""
        val = self._device.display_direction
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the display direction."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "display_direction",
            DisplayDirection.Direction[option],
        )


class SHCDisplayedTemperatureSelect(SHCEntity, SelectEntity):
    """Select entity for the temperature value shown on the thermostat display."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _DISPLAYED_TEMPERATURE_OPTIONS
    _attr_translation_key = "displayed_temperature"

    def __init__(
        self,
        device: SHCThermostat | SHCRoomThermostat2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the displayed-temperature select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_displayed_temperature"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current displayed-temperature type."""
        val = self._device.displayed_temperature
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the displayed-temperature type."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "displayed_temperature",
            DisplayedTemperatureConfiguration.DisplayedTemperature[option],
        )


class SHCValveTypeSelect(SHCEntity, SelectEntity):
    """Select entity for thermostat valve type (normally open/close)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _VALVE_TYPE_OPTIONS
    _attr_translation_key = "valve_type"

    def __init__(
        self,
        device: SHCThermostat | SHCRoomThermostat2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the valve type select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_valve_type"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current valve type."""
        val = self._device.valve_type
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the valve type."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "valve_type",
            WallThermostatConfiguration.ValveType[option],
        )


class SHCHeaterTypeSelect(SHCEntity, SelectEntity):
    """Select entity for thermostat heater type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _HEATER_TYPE_OPTIONS
    _attr_translation_key = "heater_type"

    def __init__(
        self,
        device: SHCThermostat | SHCRoomThermostat2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the heater type select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_heater_type"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current heater type."""
        val = self._device.heater_type
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the heater type."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "heater_type",
            WallThermostatConfiguration.HeaterType[option],
        )


class SHCTerminalTypeSelect(SHCEntity, SelectEntity):
    """Select entity for Room Thermostat 2 terminal (external sensor) type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _TERMINAL_TYPE_OPTIONS
    _attr_translation_key = "terminal_type"

    def __init__(
        self,
        device: SHCRoomThermostat2,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the terminal type select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_terminal_type"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current terminal type."""
        val = self._device.terminal_type
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the terminal type."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "terminal_type",
            TerminalConfiguration.Type[option],
        )


class SHCSwitchTypeSelect(SHCEntity, SelectEntity):
    """Select entity for relay / light control switch type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _SWITCH_TYPE_OPTIONS
    _attr_translation_key = "switch_type"

    def __init__(
        self,
        device: SHCMicromoduleRelay | SHCLightControl,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the switch type select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_switch_type"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current switch type."""
        val = self._device.switch_type
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the switch type."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "switch_type",
            SwitchConfiguration.SwitchType[option],
        )


class SHCActuatorTypeSelect(SHCEntity, SelectEntity):
    """Select entity for relay / light control actuator type."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _ACTUATOR_TYPE_OPTIONS
    _attr_translation_key = "actuator_type"

    def __init__(
        self,
        device: SHCMicromoduleRelay | SHCLightControl,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the actuator type select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_actuator_type"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current actuator type."""
        val = self._device.actuator_type
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the actuator type."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "actuator_type",
            SwitchConfiguration.ActuatorType[option],
        )


class SHCOutputModeSelect(SHCEntity, SelectEntity):
    """Select entity for relay / light control output mode."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = _OUTPUT_MODE_OPTIONS
    _attr_translation_key = "output_mode"

    def __init__(
        self,
        device: SHCMicromoduleRelay | SHCLightControl,
        parent_id: str,
        entry_id: str,
    ) -> None:
        """Initialize the output mode select."""
        super().__init__(device, parent_id, entry_id)
        self._attr_unique_id = f"{device.serial}_output_mode"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current output mode."""
        val = self._device.output_mode
        if val is None or val.name not in self._attr_options:
            return None
        return val.name

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the output mode."""
        await self.hass.async_add_executor_job(
            setattr,
            self._device,
            "output_mode",
            SwitchConfiguration.OutputMode[option],
        )
