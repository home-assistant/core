"""Kii Audio switch platform."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KiiAudioConfigEntry, KiiAudioCoordinator
from .entity import zone_device_info


@dataclass(frozen=True, kw_only=True)
class KiiAudioSwitchDescription(SwitchEntityDescription):
    """Description of a Kii Audio switch entity."""

    setting: str


SWITCH_DESCRIPTIONS = (
    KiiAudioSwitchDescription(
        key="tone_control",
        name="Tone Control",
        setting="audio.toneControl.enabled",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KiiAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kii Audio switch entities."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        KiiAudioZoneSwitch(coordinator, zone, description)
        for zone in coordinator.data.get("zones", [])
        if isinstance(zone, dict) and isinstance(zone.get("zoneId"), str)
        for description in SWITCH_DESCRIPTIONS
        if isinstance(_get_path(zone, f"settings.{description.setting}"), bool)
    )


class KiiAudioZoneSwitch(CoordinatorEntity[KiiAudioCoordinator], SwitchEntity):
    """Representation of a Kii Audio zone switch."""

    entity_description: KiiAudioSwitchDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KiiAudioCoordinator,
        zone: dict[str, Any],
        description: KiiAudioSwitchDescription,
    ) -> None:
        """Initialize the zone switch."""
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
    def is_on(self) -> bool | None:
        """Return whether the switch is on."""
        value = _get_path(self._settings, self.entity_description.setting)
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Request turning on the switch."""
        await self.coordinator.async_set_zone_setting(
            self._zone_id, self.entity_description.setting, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Request turning off the switch."""
        await self.coordinator.async_set_zone_setting(
            self._zone_id, self.entity_description.setting, False
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


def _get_path(target: dict[str, Any], path: str) -> Any:
    """Get a dotted path from a nested dictionary."""
    current: Any = target
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
