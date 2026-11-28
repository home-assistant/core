"""Platform for select integration."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import (
    OutdoorSirenService,
    SHCMicromoduleRelay,
    SHCMotionDetector2,
    SHCOutdoorSiren,
    SHCRoomThermostat2,
    SHCShutterContact2Plus,
    SHCSmartPlug,
    SHCSmartPlugCompact,
    SHCSmokeDetector,
    SHCThermostatGen2,
)
from boschshcpy.device import SHCDevice
from boschshcpy.services_impl import (
    DisplayDirection,
    DisplayedTemperatureConfiguration,
    PirSensorConfigurationService,
    PowerSwitchConfigurationService,
    SmokeSensitivityService,
    SwitchConfiguration,
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


@dataclass(frozen=True, kw_only=True)
class SHCSelectEntityDescription[_DeviceT: SHCDevice](SelectEntityDescription):
    """Describes a SHC select entity."""

    current_option_fn: Callable[[_DeviceT, Sequence[str] | None], str | None]
    select_option_fn: Callable[[_DeviceT, str], None]


def _siren_current_option(
    device: SHCOutdoorSiren, options: Sequence[str] | None
) -> str | None:
    """Read the Outdoor Siren's current sound level (already lowercased)."""
    try:
        return str(device.siren.sound_level.name.lower())
    except AttributeError, ValueError:
        return None


def _siren_select_option(device: SHCOutdoorSiren, option: str) -> None:
    """Write the Outdoor Siren's sound level."""
    device.siren.set_configuration(
        sound_level=OutdoorSirenService.SoundLevel[option.upper()]
    )


SIREN_SOUND_LEVEL_DESCRIPTION = SHCSelectEntityDescription[SHCOutdoorSiren](
    key="siren_sound_level",
    translation_key="siren_sound_level",
    entity_category=EntityCategory.CONFIG,
    options=["low", "medium", "high"],
    current_option_fn=_siren_current_option,
    select_option_fn=_siren_select_option,
)


def _motion_select_option(device: SHCMotionDetector2, option: str) -> None:
    """Write the Motion Detector II's motion sensitivity."""
    device.motion_sensitivity = PirSensorConfigurationService.MotionSensitivity[
        option.upper()
    ]


MOTION_SENSITIVITY_DESCRIPTION = SHCSelectEntityDescription[SHCMotionDetector2](
    key="motion_sensitivity",
    translation_key="motion_sensitivity",
    entity_category=EntityCategory.CONFIG,
    options=["high", "middle", "low"],
    current_option_fn=lambda device, options: device.motion_sensitivity.name.lower(),
    select_option_fn=_motion_select_option,
)


def _vibration_select_option(device: SHCShutterContact2Plus, option: str) -> None:
    """Write the Door/Window Contact II Plus's vibration sensitivity."""
    device.sensitivity = VibrationSensorService.SensitivityState[option.upper()]


VIBRATION_SENSITIVITY_DESCRIPTION = SHCSelectEntityDescription[SHCShutterContact2Plus](
    key="vibration_sensitivity",
    translation_key="vibration_sensitivity",
    entity_category=EntityCategory.CONFIG,
    options=["very_high", "high", "medium", "low", "very_low"],
    current_option_fn=lambda device, options: device.sensitivity.name.lower(),
    select_option_fn=_vibration_select_option,
)


def _smoke_select_option(device: SHCSmokeDetector, option: str) -> None:
    """Write the Smoke Detector's smoke sensitivity."""
    device.smoke_sensitivity = SmokeSensitivityService.SmokeSensitivityLevel[
        option.upper()
    ]


SMOKE_SENSITIVITY_DESCRIPTION = SHCSelectEntityDescription[SHCSmokeDetector](
    key="smoke_sensitivity",
    translation_key="smoke_sensitivity",
    entity_category=EntityCategory.CONFIG,
    options=["high", "middle", "low"],
    current_option_fn=lambda device, options: (
        level.name.lower() if (level := device.smoke_sensitivity) else None
    ),
    select_option_fn=_smoke_select_option,
)


def _display_direction_select_option(
    device: SHCThermostatGen2 | SHCRoomThermostat2, option: str
) -> None:
    """Write the thermostat's display direction."""
    device.display_direction = DisplayDirection.Direction[option.upper()]


DISPLAY_DIRECTION_DESCRIPTION = SHCSelectEntityDescription[
    SHCThermostatGen2 | SHCRoomThermostat2
](
    key="display_direction",
    translation_key="display_direction",
    entity_category=EntityCategory.CONFIG,
    options=["normal", "reversed"],
    current_option_fn=lambda device, options: (
        direction.name.lower() if (direction := device.display_direction) else None
    ),
    select_option_fn=_display_direction_select_option,
)


def _displayed_temperature_select_option(
    device: SHCThermostatGen2 | SHCRoomThermostat2, option: str
) -> None:
    """Write which temperature the thermostat display shows."""
    device.displayed_temperature = (
        DisplayedTemperatureConfiguration.DisplayedTemperature[option.upper()]
    )


DISPLAYED_TEMPERATURE_DESCRIPTION = SHCSelectEntityDescription[
    SHCThermostatGen2 | SHCRoomThermostat2
](
    key="displayed_temperature",
    translation_key="displayed_temperature",
    entity_category=EntityCategory.CONFIG,
    options=["setpoint", "measured"],
    current_option_fn=lambda device, options: (
        shown.name.lower() if (shown := device.displayed_temperature) else None
    ),
    select_option_fn=_displayed_temperature_select_option,
)


def _state_after_power_outage_select_option(
    device: SHCSmartPlug | SHCSmartPlugCompact, option: str
) -> None:
    """Write the Smart Plug's state after a power outage."""
    device.state_after_power_outage = (
        PowerSwitchConfigurationService.StateAfterPowerOutage[option.upper()]
    )


STATE_AFTER_POWER_OUTAGE_DESCRIPTION = SHCSelectEntityDescription[
    SHCSmartPlug | SHCSmartPlugCompact
](
    key="state_after_power_outage",
    translation_key="state_after_power_outage",
    entity_category=EntityCategory.CONFIG,
    options=["off", "on", "last_state"],
    current_option_fn=lambda device, options: (
        state.name.lower() if (state := device.state_after_power_outage) else None
    ),
    select_option_fn=_state_after_power_outage_select_option,
)


def _valve_type_select_option(device: SHCThermostatGen2, option: str) -> None:
    """Write the thermostat's valve type."""
    device.valve_type = WallThermostatConfiguration.ValveType[option.upper()]


VALVE_TYPE_DESCRIPTION = SHCSelectEntityDescription[SHCThermostatGen2](
    key="valve_type",
    translation_key="valve_type",
    entity_category=EntityCategory.CONFIG,
    options=["normally_close", "normally_open"],
    current_option_fn=lambda device, options: (
        valve.name.lower() if (valve := device.valve_type) else None
    ),
    select_option_fn=_valve_type_select_option,
)


def _heater_type_select_option(device: SHCThermostatGen2, option: str) -> None:
    """Write the thermostat's heater type."""
    device.heater_type = WallThermostatConfiguration.HeaterType[option.upper()]


HEATER_TYPE_DESCRIPTION = SHCSelectEntityDescription[SHCThermostatGen2](
    key="heater_type",
    translation_key="heater_type",
    entity_category=EntityCategory.CONFIG,
    options=[
        "floor_heating",
        "floor_heating_low_energy",
        "radiator",
        "convector_passive",
        "convector_active",
        "volt_free_heating",
    ],
    current_option_fn=lambda device, options: (
        heater.name.lower() if (heater := device.heater_type) else None
    ),
    select_option_fn=_heater_type_select_option,
)


def _switch_type_select_option(device: SHCMicromoduleRelay, option: str) -> None:
    """Write the relay's switch type."""
    device.switch_type = SwitchConfiguration.SwitchType[option.upper()]


SWITCH_TYPE_DESCRIPTION = SHCSelectEntityDescription[SHCMicromoduleRelay](
    key="switch_type",
    translation_key="switch_type",
    entity_category=EntityCategory.CONFIG,
    options=[
        "none",
        "pushbutton",
        "switch",
        "no_switch",
    ],
    current_option_fn=lambda device, options: (
        value.name.lower() if (value := device.switch_type) else None
    ),
    select_option_fn=_switch_type_select_option,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC select platform."""
    session = config_entry.runtime_data
    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[SHCSelect] = []
    entities.extend(
        SHCSelect(
            hass=hass,
            device=siren,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SIREN_SOUND_LEVEL_DESCRIPTION,
        )
        for siren in session.device_helper.outdoor_sirens
        if siren.siren is not None
    )

    motion_detectors: list[SHCMotionDetector2] = []
    for detector in session.device_helper.motion_detectors2:
        try:
            _ = detector.motion_sensitivity
        except AttributeError:
            continue
        motion_detectors.append(detector)

    entities.extend(
        SHCSelect(
            hass=hass,
            device=detector,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=MOTION_SENSITIVITY_DESCRIPTION,
        )
        for detector in motion_detectors
    )

    entities.extend(
        SHCSelect(
            hass=hass,
            device=contact,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=VIBRATION_SENSITIVITY_DESCRIPTION,
        )
        for contact in session.device_helper.shutter_contacts2
        if isinstance(contact, SHCShutterContact2Plus)
    )

    entities.extend(
        SHCSelect(
            hass=hass,
            device=smoke_detector,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SMOKE_SENSITIVITY_DESCRIPTION,
        )
        for smoke_detector in session.device_helper.smoke_detectors
        if smoke_detector.smoke_sensitivity is not None
    )

    thermostats = [
        thermostat
        for thermostat in (
            *session.device_helper.thermostats,
            *session.device_helper.roomthermostats,
        )
        if isinstance(thermostat, (SHCThermostatGen2, SHCRoomThermostat2))
    ]
    entities.extend(
        SHCSelect(
            hass=hass,
            device=thermostat,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=DISPLAY_DIRECTION_DESCRIPTION,
        )
        for thermostat in thermostats
        if thermostat.supports_display_direction
    )
    entities.extend(
        SHCSelect(
            hass=hass,
            device=thermostat,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=DISPLAYED_TEMPERATURE_DESCRIPTION,
        )
        for thermostat in thermostats
        if thermostat.supports_displayed_temperature
    )

    entities.extend(
        SHCSelect(
            hass=hass,
            device=plug,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=STATE_AFTER_POWER_OUTAGE_DESCRIPTION,
        )
        for plug in session.device_helper.smart_plugs
        if plug.state_after_power_outage is not None
    )

    entities.extend(
        SHCSelect(
            hass=hass,
            device=compact_plug,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=STATE_AFTER_POWER_OUTAGE_DESCRIPTION,
        )
        for compact_plug in session.device_helper.smart_plugs_compact
        if compact_plug.state_after_power_outage is not None
    )

    entities.extend(
        SHCSelect(
            hass=hass,
            device=thermostat,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=VALVE_TYPE_DESCRIPTION,
        )
        for thermostat in session.device_helper.thermostats
        if isinstance(thermostat, SHCThermostatGen2)
        and thermostat.supports_wall_thermostat_configuration
        and thermostat.valve_type is not None
    )
    entities.extend(
        SHCSelect(
            hass=hass,
            device=thermostat,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=HEATER_TYPE_DESCRIPTION,
        )
        for thermostat in session.device_helper.thermostats
        if isinstance(thermostat, SHCThermostatGen2)
        and thermostat.supports_wall_thermostat_configuration
        and thermostat.heater_type is not None
    )
    entities.extend(
        SHCSelect(
            hass=hass,
            device=relay,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SWITCH_TYPE_DESCRIPTION,
        )
        for relay in session.device_helper.micromodule_relays
        if relay.supports_switch_configuration and relay.switch_type is not None
    )

    async_add_entities(entities)


class SHCSelect[_DeviceT: SHCDevice](SHCEntity, SelectEntity):
    """Generic SHC select entity, driven by a SHCSelectEntityDescription."""

    entity_description: SHCSelectEntityDescription[_DeviceT]
    _device: _DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        parent_id: str,
        entry_id: str,
        description: SHCSelectEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the select entity."""
        self.entity_description = description
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        self._attr_unique_id = f"{device.serial}_{description.key}"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.entity_description.current_option_fn(self._device, self.options)

    @override
    def select_option(self, option: str) -> None:
        """Select an option, writing it to the device."""
        self.entity_description.select_option_fn(self._device, option)
