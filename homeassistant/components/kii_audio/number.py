"""Kii Audio number platform."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfSoundPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KiiAudioConfigEntry, KiiAudioCoordinator
from .entity import zone_device_info

TONE_CONTROL_MIN = -6.0
TONE_CONTROL_MAX = 6.0
TONE_CONTROL_SIMPLE_STEP = 0.5
TONE_CONTROL_ADVANCED_STEP = 0.1


@dataclass(frozen=True, kw_only=True)
class KiiAudioNumberDescription(NumberEntityDescription):
    """Description of a Kii Audio number entity."""

    setting: str


TONE_CONTROL_DESCRIPTIONS = (
    KiiAudioNumberDescription(
        key="bass",
        name="Bass",
        setting="audio.toneControl.low.gain",
    ),
    KiiAudioNumberDescription(
        key="treble",
        name="Treble",
        setting="audio.toneControl.high.gain",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KiiAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kii Audio number entities."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        KiiAudioToneControlNumber(coordinator, zone, description)
        for zone in coordinator.data.get("zones", [])
        if isinstance(zone, dict)
        and isinstance(zone.get("zoneId"), str)
        and _has_tone_control(zone)
        for description in TONE_CONTROL_DESCRIPTIONS
    )


class KiiAudioToneControlNumber(CoordinatorEntity[KiiAudioCoordinator], NumberEntity):
    """Representation of a Kii Audio tone control number."""

    entity_description: KiiAudioNumberDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_native_max_value = TONE_CONTROL_MAX
    _attr_native_min_value = TONE_CONTROL_MIN
    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: KiiAudioCoordinator,
        zone: dict[str, Any],
        description: KiiAudioNumberDescription,
    ) -> None:
        """Initialize the tone control number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_id = zone["zoneId"]
        self._attr_name = (
            description.name if isinstance(description.name, str) else None
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{self._zone_id}_{description.key}"
        )
        self._attr_device_info = zone_device_info(coordinator, self._zone_id, zone)

    @property
    def native_step(self) -> float:
        """Return the tone control step for the current zone mode."""
        if self._settings.get("advancedMode") is True:
            return TONE_CONTROL_ADVANCED_STEP
        return TONE_CONTROL_SIMPLE_STEP

    @property
    def native_value(self) -> float | None:
        """Return the current tone control value."""
        value = _get_path(self._settings, self.entity_description.setting)
        return float(value) if isinstance(value, int | float) else None

    async def async_set_native_value(self, value: float) -> None:
        """Request a tone control change."""
        step = self.native_step
        rounded_value = round(value / step) * step
        rounded_value = max(TONE_CONTROL_MIN, min(TONE_CONTROL_MAX, rounded_value))
        await self.coordinator.async_set_zone_setting(
            self._zone_id,
            self.entity_description.setting,
            rounded_value,
        )

    @property
    def _zone(self) -> dict[str, Any]:
        """Return the latest zone data."""
        zones = self.coordinator.data.get("zones", [])
        for zone in zones:
            if isinstance(zone, dict) and zone.get("zoneId") == self._zone_id:
                return zone
        return {}

    @property
    def _settings(self) -> dict[str, Any]:
        """Return the latest zone settings."""
        settings = self._zone.get("settings")
        return settings if isinstance(settings, dict) else {}


def _has_tone_control(zone: dict[str, Any]) -> bool:
    """Return whether zone data has tone control settings."""
    return isinstance(_get_path(zone, "settings.audio.toneControl"), dict)


def _get_path(target: dict[str, Any], path: str) -> Any:
    """Get a dotted path from a nested dictionary."""
    current: Any = target
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
