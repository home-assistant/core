"""Platform for button integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from boschshcpy import (
    SHCMicromoduleDimmer,
    SHCMotionDetector2,
    SHCOutdoorSiren,
    SHCSmartPlug,
    SHCSmartPlugCompact,
    SHCSmokeDetector,
    SHCWaterAlarmSystem,
)
from boschshcpy.device import SHCDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .const import DOMAIN
from .entity import SHCEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SHCButtonEntityDescription[_DeviceT: SHCDevice](ButtonEntityDescription):
    """Describes a SHC button entity."""

    press_fn: Callable[[_DeviceT], None]


SMOKE_TEST_DESCRIPTION = SHCButtonEntityDescription[SHCSmokeDetector](
    key="smoke_test",
    translation_key="smoke_test",
    entity_category=EntityCategory.DIAGNOSTIC,
    press_fn=lambda device: device.smoketest_requested(),
)

TAMPER_RESET_DESCRIPTION = SHCButtonEntityDescription[SHCMotionDetector2](
    key="reset_tamper",
    translation_key="reset_tamper",
    entity_category=EntityCategory.DIAGNOSTIC,
    press_fn=lambda device: device.reset_tampered_state(),
)

SIREN_TEST_ALARM_DESCRIPTION = SHCButtonEntityDescription[SHCOutdoorSiren](
    key="siren_test_alarm",
    translation_key="siren_test_alarm",
    entity_category=EntityCategory.DIAGNOSTIC,
    press_fn=lambda device: device.trigger_test_alarm(),
)

RESET_ENERGY_DESCRIPTION = SHCButtonEntityDescription[
    SHCSmartPlug | SHCSmartPlugCompact
](
    key="reset_energy_summation",
    translation_key="reset_energy_summation",
    entity_category=EntityCategory.CONFIG,
    press_fn=lambda device: device.reset_energy_summation(),
)


def _preview_max_brightness(device: SHCMicromoduleDimmer) -> None:
    """Flash the dimmer's load at maximum brightness."""
    if TYPE_CHECKING:
        assert device.dimmer_configuration is not None
    device.dimmer_configuration.preview_max_brightness()


def _preview_min_brightness(device: SHCMicromoduleDimmer) -> None:
    """Flash the dimmer's load at minimum brightness."""
    if TYPE_CHECKING:
        assert device.dimmer_configuration is not None
    device.dimmer_configuration.preview_min_brightness()


PREVIEW_MAX_BRIGHTNESS_DESCRIPTION = SHCButtonEntityDescription[SHCMicromoduleDimmer](
    key="preview_max_brightness",
    translation_key="preview_max_brightness",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    press_fn=_preview_max_brightness,
)

PREVIEW_MIN_BRIGHTNESS_DESCRIPTION = SHCButtonEntityDescription[SHCMicromoduleDimmer](
    key="preview_min_brightness",
    translation_key="preview_min_brightness",
    entity_category=EntityCategory.CONFIG,
    entity_registry_enabled_default=False,
    press_fn=_preview_min_brightness,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC button platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    entities: list[SHCButton] = [
        SHCButton(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SMOKE_TEST_DESCRIPTION,
        )
        for device in session.device_helper.smoke_detectors
    ]
    entities.extend(
        SHCButton(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=TAMPER_RESET_DESCRIPTION,
        )
        for device in session.device_helper.motion_detectors2
        if device.supports_tamper_reset
    )
    entities.extend(
        SHCButton(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=SIREN_TEST_ALARM_DESCRIPTION,
        )
        for device in session.device_helper.outdoor_sirens
    )
    entities.extend(
        SHCButton(
            hass=hass,
            device=plug,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=RESET_ENERGY_DESCRIPTION,
        )
        for plug in (
            *session.device_helper.smart_plugs,
            *session.device_helper.smart_plugs_compact,
        )
    )
    entities.extend(
        SHCButton(
            hass=hass,
            device=dimmer,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
            description=description,
        )
        for dimmer in session.device_helper.micromodule_dimmers
        if dimmer.supports_dimmer_configuration
        for description in (
            PREVIEW_MAX_BRIGHTNESS_DESCRIPTION,
            PREVIEW_MIN_BRIGHTNESS_DESCRIPTION,
        )
    )
    if (water_alarm := session.water_alarm_system) is not None:
        async_add_entities(
            [
                *entities,
                SHCWaterAlarmMuteButton(
                    hass=hass, device=water_alarm, entry_id=config_entry.entry_id
                ),
            ]
        )
        return
    async_add_entities(entities)


class SHCButton[_DeviceT: SHCDevice](SHCEntity, ButtonEntity):
    """Generic SHC button entity, driven by a SHCButtonEntityDescription."""

    entity_description: SHCButtonEntityDescription[_DeviceT]
    _device: _DeviceT

    def __init__(
        self,
        hass: HomeAssistant,
        device: _DeviceT,
        parent_id: str,
        entry_id: str,
        description: SHCButtonEntityDescription[_DeviceT],
    ) -> None:
        """Initialize the button entity."""
        self.entity_description = description
        super().__init__(
            hass=hass, device=device, parent_id=parent_id, entry_id=entry_id
        )
        self._attr_unique_id = f"{device.serial}_{description.key}"

    @override
    def press(self) -> None:
        """Press the button."""
        self.entity_description.press_fn(self._device)


class SHCWaterAlarmMuteButton(ButtonEntity):
    """Button that mutes a triggered water alarm."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "water_alarm_mute"

    def __init__(
        self, hass: HomeAssistant, device: SHCWaterAlarmSystem, entry_id: str
    ) -> None:
        """Initialize the mute button on the water alarm system's device."""
        self._device = device
        self._attr_unique_id = f"{device.root_device_id}_{device.id}_mute"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            translation_key="water_alarm_system",
            manufacturer=device.manufacturer,
            model=device.device_model,
        )
        if device.root_device_id is not None and (
            hub := dr.async_get(hass).async_get_device_by_identifier(
                (DOMAIN, device.root_device_id), entry_id
            )
        ):
            device_info.via_device_id = hub.id
        self._attr_device_info = device_info

    @override
    def press(self) -> None:
        """Mute the active water alarm."""
        self._device.mute()
