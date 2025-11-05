"""TOLO Sauna switch controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tololib import ToloClient, ToloStatus

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ToloConfigEntry, ToloSaunaUpdateCoordinator
from .entity import ToloSaunaCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class ToloSwitchEntityDescription(SwitchEntityDescription):
    """Class describing TOLO switch entities."""

    getter: Callable[[ToloStatus], bool]
    setter: Callable[[ToloClient, bool], bool]


SWITCHES = (
    ToloSwitchEntityDescription(
        key="aroma_therapy_on",
        translation_key="aroma_therapy_on",
        getter=lambda status: status.aroma_therapy_on,
        setter=lambda client, value: client.set_aroma_therapy_on(value),
    ),
    ToloSwitchEntityDescription(
        key="salt_bath_on",
        translation_key="salt_bath_on",
        getter=lambda status: status.salt_bath_on,
        setter=lambda client, value: client.set_salt_bath_on(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch controls for TOLO Sauna."""
    coordinator = entry.runtime_data
    async_add_entities(
        ToloSwitchEntity(coordinator, entry, description) for description in SWITCHES
    )


class ToloSwitchEntity(ToloSaunaCoordinatorEntity, SwitchEntity):
    """TOLO switch entity."""

    entity_description: ToloSwitchEntityDescription

    def __init__(
        self,
        coordinator: ToloSaunaUpdateCoordinator,
        entry: ToloConfigEntry,
        entity_description: ToloSwitchEntityDescription,
    ) -> None:
        """Initialize TOLO switch entity."""
        super().__init__(coordinator, entry)
        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return if the switch is currently on."""
        return self.entity_description.getter(self.coordinator.data.status)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.entity_description.setter(self.coordinator.client, True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self.entity_description.setter(self.coordinator.client, False)
