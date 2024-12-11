"""Plugwise Select component for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugwiseConfigEntry
from .const import SelectOptionsType, SelectType
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command


@dataclass(frozen=True, kw_only=True)
class PlugwiseSelectEntityDescription(SelectEntityDescription):
    """Class describing Plugwise Select entities."""

    key: SelectType
    options_key: SelectOptionsType


SELECT_TYPES = (
    PlugwiseSelectEntityDescription(
        key="select_schedule",
        translation_key="select_schedule",
        options_key="available_schedules",
    ),
    PlugwiseSelectEntityDescription(
        key="select_regulation_mode",
        translation_key="regulation_mode",
        entity_category=EntityCategory.CONFIG,
        options_key="regulation_modes",
    ),
    PlugwiseSelectEntityDescription(
        key="select_dhw_mode",
        translation_key="dhw_mode",
        entity_category=EntityCategory.CONFIG,
        options_key="dhw_modes",
    ),
    PlugwiseSelectEntityDescription(
        key="select_gateway_mode",
        translation_key="gateway_mode",
        entity_category=EntityCategory.CONFIG,
        options_key="gateway_modes",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile selector from a config entry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities."""
        if not coordinator.new_devices:
            return

        async_add_entities(
            PlugwiseSelectEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            for description in SELECT_TYPES
            if description.options_key in coordinator.data.devices[device_id]
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseSelectEntity(PlugwiseEntity, SelectEntity):
    """Represent Smile selector."""

    entity_description: PlugwiseSelectEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        entity_description: PlugwiseSelectEntityDescription,
    ) -> None:
        """Initialise the selector."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}-{entity_description.key}"
        self.entity_description = entity_description

        self._location = device_id
        if (location := self.device.get("location")) is not None:
            self._location = location

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        return self.device[self.entity_description.key]

    @property
    def options(self) -> list[str]:
        """Return the available select-options."""
        return self.device[self.entity_description.options_key]

    @plugwise_command
    async def async_select_option(self, option: str) -> None:
        """Change to the selected entity option.

        self._location and STATE_ON are required for the thermostat-schedule select.
        """
        await self.coordinator.api.set_select(
            self.entity_description.key, self._location, option, STATE_ON
        )
