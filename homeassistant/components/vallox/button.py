"""Support for Vallox buttons."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from vallox_websocket_api import Vallox

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import DOMAIN


class ValloxButtonEntity(ValloxEntity, ButtonEntity):
    """Representation of a Vallox button."""

    entity_description: ValloxButtonEntityDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxButtonEntityDescription,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox button."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client


class ValloxResetFilterButton(ValloxButtonEntity):
    """Representation of a Vallox reset filter button."""

    async def async_press(self) -> None:
        """Press the button."""
        await self._client.set_filter_change_date(date.today())
        await self.coordinator.async_request_refresh()


@dataclass(frozen=True)
class ValloxButtonEntityDescription(ButtonEntityDescription):
    """Describes Vallox button entity."""


BUTTON_ENTITIES: tuple[ValloxButtonEntityDescription, ...] = (
    ValloxButtonEntityDescription(
        key="reset_filter", translation_key="reset_filter", icon="mdi:air-filter"
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
            ValloxResetFilterButton(
                data["name"], data["coordinator"], description, data["client"]
            )
            for description in BUTTON_ENTITIES
        ]
    )
