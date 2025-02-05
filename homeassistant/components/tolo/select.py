"""TOLO Sauna Select controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tololib import ToloClient, ToloSettings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCESSORY_AROMA_THERAPY,
    CONF_ACCESSORY_LIGHT,
    DOMAIN,
    AromaTherapySlot,
    LampMode,
)
from .coordinator import ToloSaunaUpdateCoordinator
from .entity import ToloEntityDescription, ToloSaunaCoordinatorEntity, has_accessory


@dataclass(frozen=True, kw_only=True)
class ToloSelectEntityDescription(ToloEntityDescription, SelectEntityDescription):
    """Class describing TOLO select entities."""

    options: list[str]
    getter: Callable[[ToloSettings], str]
    setter: Callable[[ToloClient, str], bool]


SELECTS = (
    ToloSelectEntityDescription(
        key="lamp_mode",
        translation_key="lamp_mode",
        options=[lamp_mode.name.lower() for lamp_mode in LampMode],
        getter=lambda settings: settings.lamp_mode.name.lower(),
        setter=lambda client, option: client.set_lamp_mode(
            LampMode[option.upper()].value
        ),
        accessory_required=CONF_ACCESSORY_LIGHT,
    ),
    ToloSelectEntityDescription(
        key="aroma_therapy_slot",
        translation_key="aroma_therapy_slot",
        options=[
            aroma_therapy_slot.name.lower() for aroma_therapy_slot in AromaTherapySlot
        ],
        getter=lambda settings: settings.aroma_therapy_slot.name.lower(),
        setter=lambda client, option: client.set_aroma_therapy_slot(
            AromaTherapySlot[option.upper()].value
        ),
        accessory_required=CONF_ACCESSORY_AROMA_THERAPY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ToloSelectEntity(coordinator, entry, description)
        for description in SELECTS
        if has_accessory(entry, description.accessory_required)
    )


class ToloSelectEntity(ToloSaunaCoordinatorEntity, SelectEntity):
    """TOLO select entity."""

    _attr_entity_category = EntityCategory.CONFIG

    entity_description: ToloSelectEntityDescription

    def __init__(
        self,
        coordinator: ToloSaunaUpdateCoordinator,
        entry: ConfigEntry,
        entity_description: ToloSelectEntityDescription,
    ) -> None:
        """Initialize TOLO select entity."""
        super().__init__(coordinator, entry)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"

    @property
    def options(self) -> list[str]:
        """Return available select options."""
        return self.entity_description.options

    @property
    def current_option(self) -> str:
        """Return current select option."""
        return self.entity_description.getter(self.coordinator.data.settings)

    def select_option(self, option: str) -> None:
        """Select a select option."""
        self.entity_description.setter(self.coordinator.client, option)
