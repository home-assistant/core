"""Support for Vallox buttons."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from vallox_websocket_api import Vallox

from homeassistant.components.date import DateEntity, DateEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import DOMAIN


class ValloxFilterChangeDate(ValloxEntity, DateEntity):
    """Representation of a Vallox date."""

    entity_description: ValloxDateEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxDateEntityDescription,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox date."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client

    @property
    def native_value(self) -> date | None:
        """Return the latest value."""

        return self.coordinator.data.filter_change_date

    async def async_set_value(self, value: date) -> None:
        """Change the date."""

        await self._client.set_filter_change_date(value)
        await self.coordinator.async_request_refresh()


@dataclass(frozen=True)
class ValloxDateEntityDescription(DateEntityDescription):
    """Describes Vallox date entity."""


DATE_ENTITIES: tuple[ValloxDateEntityDescription, ...] = (
    ValloxDateEntityDescription(
        key="filter_change_date",
        translation_key="filter_change_date",
        icon="mdi:air-filter",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the buttons."""

    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ValloxFilterChangeDate(
                data["name"], data["coordinator"], description, data["client"]
            )
            for description in DATE_ENTITIES
        ]
    )
