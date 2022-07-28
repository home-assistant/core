"""Support for Vallox ventilation unit selects."""
from __future__ import annotations

from dataclasses import dataclass

from vallox_websocket_api import Vallox

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import (
    DOMAIN,
    STR_TO_VALLOX_PROFILE_SETTABLE,
    VALLOX_PROFILE_TO_STR_REPORTABLE,
)


class ValloxSelectEntity(ValloxEntity, SelectEntity):
    """Representation of a Vallox select entity."""

    entity_description: ValloxSelectEntityDescription
    _attr_has_entity_name = True
    _attr_entity_category: EntityCategory | None = EntityCategory.CONFIG

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxSelectEntityDescription,
        client: Vallox,
    ) -> None:
        """Initialize the Vallox sensor."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"
        self._client = client


@dataclass
class ValloxSelectEntityDescription(SelectEntityDescription):
    """Describes Vallox select entity."""

    metric_key: str | None = None
    entity_type: type[ValloxSelectEntity] = ValloxSelectEntity
    current_option: str | None = None
    options: list[str] | None = None


class ValloxProfileEntity(ValloxSelectEntity):
    """Child class for profile reporting."""

    _attr_options = list(STR_TO_VALLOX_PROFILE_SETTABLE.keys())

    @property
    def current_option(self) -> str:
        """Return the value reported by the sensor."""
        vallox_profile = self.coordinator.data.profile
        return str(VALLOX_PROFILE_TO_STR_REPORTABLE.get(vallox_profile))

    async def async_select_option(self, option: str) -> None:
        """Change profile."""
        await self._client.set_profile(STR_TO_VALLOX_PROFILE_SETTABLE[option])
        await self.coordinator.async_request_refresh()


SELECT_ENTITIES: tuple[ValloxSelectEntityDescription, ...] = (
    ValloxSelectEntityDescription(
        key="profile",
        name="Profile",
        icon="mdi:gauge",
        entity_type=ValloxProfileEntity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            description.entity_type(
                data["name"], data["coordinator"], description, data["client"]
            )
            for description in SELECT_ENTITIES
        ]
    )
