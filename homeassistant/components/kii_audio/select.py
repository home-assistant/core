"""Kii Audio select platform."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KiiAudioConfigEntry, KiiAudioCoordinator
from .entity import zone_device_info

ANALOG_SENSITIVITY_OPTIONS = ["Low", "High"]
ANALOG_SENSITIVITY_TO_VALUE = {"Low": False, "High": True}
ANALOG_SENSITIVITY_FROM_VALUE = {False: "Low", True: "High"}

LATENCY_OPTIONS = {
    "optimum": "Optimum",
    "minimum": "Minimum",
    "match": "Match Kii Three",
}
LATENCY_TO_VALUE = {name: value for value, name in LATENCY_OPTIONS.items()}


def _analog_current(value: Any) -> str | None:
    """Return the current analogue sensitivity option."""
    return ANALOG_SENSITIVITY_FROM_VALUE.get(value) if isinstance(value, bool) else None


def _analog_value(option: str) -> bool:
    """Return the Kii value for an analogue sensitivity option."""
    return ANALOG_SENSITIVITY_TO_VALUE[option]


def _latency_current(value: Any) -> str | None:
    """Return the current latency option."""
    return LATENCY_OPTIONS.get(value) if isinstance(value, str) else None


def _latency_value(option: str) -> str:
    """Return the Kii value for a latency option."""
    return LATENCY_TO_VALUE[option]


@dataclass(frozen=True, kw_only=True)
class KiiAudioSelectDescription(SelectEntityDescription):
    """Description of a Kii Audio select entity."""

    setting: str
    options: list[str]
    current_option_fn: Callable[[Any], str | None]
    value_fn: Callable[[str], Any]


SELECT_DESCRIPTIONS = (
    KiiAudioSelectDescription(
        key="analog_input_sensitivity",
        name="Analogue Input Sensitivity",
        setting="audio.analogHighSensitivity",
        options=ANALOG_SENSITIVITY_OPTIONS,
        current_option_fn=_analog_current,
        value_fn=_analog_value,
    ),
    KiiAudioSelectDescription(
        key="latency",
        name="Latency",
        setting="audio.latency",
        options=list(LATENCY_OPTIONS.values()),
        current_option_fn=_latency_current,
        value_fn=_latency_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KiiAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kii Audio select entities."""
    coordinator = config_entry.runtime_data
    async_add_entities(
        KiiAudioZoneSelect(coordinator, zone, description)
        for zone in coordinator.data.get("zones", [])
        if isinstance(zone, dict) and isinstance(zone.get("zoneId"), str)
        for description in SELECT_DESCRIPTIONS
        if _get_path(zone, f"settings.{description.setting}") is not None
    )


class KiiAudioZoneSelect(CoordinatorEntity[KiiAudioCoordinator], SelectEntity):
    """Representation of a Kii Audio zone select."""

    entity_description: KiiAudioSelectDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KiiAudioCoordinator,
        zone: dict[str, Any],
        description: KiiAudioSelectDescription,
    ) -> None:
        """Initialize the zone select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_id = zone["zoneId"]
        self._attr_name = (
            description.name if isinstance(description.name, str) else None
        )
        self._attr_options = list(description.options)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}_{self._zone_id}_{description.key}"
        )
        self._attr_device_info = zone_device_info(coordinator, self._zone_id, zone)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = _get_path(self._settings, self.entity_description.setting)
        return self.entity_description.current_option_fn(value)

    async def async_select_option(self, option: str) -> None:
        """Request a select option change."""
        if option not in self.entity_description.options:
            return
        await self.coordinator.async_set_zone_setting(
            self._zone_id,
            self.entity_description.setting,
            self.entity_description.value_fn(option),
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
