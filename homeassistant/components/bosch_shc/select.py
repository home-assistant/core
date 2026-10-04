"""Platform for select integration."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import OutdoorSirenService, SHCMotionDetector2, SHCOutdoorSiren
from boschshcpy.device import SHCDevice
from boschshcpy.services_impl import PirSensorConfigurationService

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
    siren = device.siren
    siren.put_state_element(
        "outdoorSirenConfiguration",
        {
            "alarmDuration": siren.alarm_duration,
            "flashDuration": siren.flash_duration,
            "soundLevel": OutdoorSirenService.SoundLevel[option.upper()].value,
            "alarmDelay": siren.alarm_delay,
            "flashDelay": siren.flash_delay,
        },
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

    async_add_entities(
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

    async_add_entities(
        SHCSelect(
            hass=hass,
            device=detector,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=MOTION_SENSITIVITY_DESCRIPTION,
        )
        for detector in motion_detectors
    )


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
