"""Support for openSenseMap Air Quality data."""

from typing import override

from homeassistant.components.air_quality import (
    DOMAIN as AIR_QUALITY_DOMAIN,
    AirQualityEntity,
)
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import AIR_QUALITY_DEPRECATION_BREAKS_IN_VERSION, CONF_STATION_ID, DOMAIN
from .coordinator import OpenSenseMapConfigEntry, OpenSenseMapCoordinator


def _automations_and_scripts_using_entity(
    hass: HomeAssistant, entity_id: str
) -> list[str]:
    """Return markdown links to automations and scripts referencing an entity."""
    automations = automations_with_entity(hass, entity_id)
    scripts = scripts_with_entity(hass, entity_id)
    if not automations and not scripts:
        return []

    entity_registry = er.async_get(hass)
    items: list[str] = []
    for integration, entities in (("automation", automations), ("script", scripts)):
        for used_entity_id in entities:
            if entry := entity_registry.async_get(used_entity_id):
                items.append(
                    f"- [{entry.original_name}]"
                    f"(/config/{integration}/edit/{entry.unique_id})"
                )
            else:
                items.append(f"- `{used_entity_id}`")
    return items


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenSenseMapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the openSenseMap air quality entity from a config entry.

    The air quality entity is deprecated in favor of the individual particulate
    matter sensor entities. It is only kept for existing installations that
    already have it registered; fresh installations no longer create it.
    """
    station_id = entry.data[CONF_STATION_ID]
    issue_id = f"deprecated_air_quality_{entry.entry_id}"
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        AIR_QUALITY_DOMAIN, DOMAIN, station_id
    )

    if entity_id is None:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    items = _automations_and_scripts_using_entity(hass, entity_id)
    entity_entry = entity_registry.async_get(entity_id)
    if entity_entry is not None and entity_entry.disabled and not items:
        # Disabled and unused: clean it up instead of carrying it forward.
        entity_registry.async_remove(entity_id)
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    translation_key = "deprecated_air_quality"
    placeholders = {"entity_id": entity_id}
    if items:
        translation_key = "deprecated_air_quality_in_use"
        placeholders["items"] = "\n".join(items)

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=AIR_QUALITY_DEPRECATION_BREAKS_IN_VERSION,
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )

    async_add_entities(
        [OpenSenseMapQuality(entry.runtime_data, station_id, entry.title)]
    )


class OpenSenseMapQuality(CoordinatorEntity[OpenSenseMapCoordinator], AirQualityEntity):
    """Implementation of an openSenseMap air quality entity."""

    _attr_attribution = "Data provided by openSenseMap"

    def __init__(
        self, coordinator: OpenSenseMapCoordinator, station_id: str, name: str
    ) -> None:
        """Initialize the air quality entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = station_id

    @property
    @override
    def particulate_matter_2_5(self) -> float | None:
        """Return the particulate matter 2.5 level."""
        return self.coordinator.data.pm2_5.value

    @property
    @override
    def particulate_matter_10(self) -> float | None:
        """Return the particulate matter 10 level."""
        return self.coordinator.data.pm10.value
