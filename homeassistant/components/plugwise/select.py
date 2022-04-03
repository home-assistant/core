"""Plugwise Select component for Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity


@dataclass
class PlugwiseSelectDescriptionMixin:
    """Mixin values for Plugwise Select entities."""

    command: str
    current_option: str
    options: str


@dataclass
class PlugwiseSelectEntityDescription(
    SelectEntityDescription, PlugwiseSelectDescriptionMixin
):
    """Class describing Plugwise Number entities."""


SELECT_TYPES = (
    PlugwiseSelectEntityDescription(
        key="select_schedule",
        name="Thermostat Schedule",
        icon="mdi:calendar-clock",
        command="set_schedule_state",
        current_option="selected_schedule",
        options="available_schedules",
    ),
    PlugwiseSelectEntityDescription(
        key="select_regulation_mode",
        name="Regulation Mode",
        icon="mdi:hvac",
        entity_category=EntityCategory.CONFIG,
        command="set_regulation_mode",
        current_option="regulation_mode",
        options="regulation_modes",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile selector from a config entry."""
    coordinator: PlugwiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[PlugwiseSelectEntity] = []
    for device_id, device in coordinator.data.devices.items():
        for description in SELECT_TYPES:
            if (
                description.options in device
                and len(device.get(description.options, [])) > 1
            ):
                entities.append(
                    PlugwiseSelectEntity(coordinator, device_id, description)
                )

    async_add_entities(entities)


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
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"
        self._attr_name = (
            f"{self.device.get('name', '')} {entity_description.name}"
        ).lstrip()

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.device.get(self.entity_description.current_option)

    @property
    def options(self) -> list[str]:
        """Return the selectable entity options."""
        return self.device.get(self.entity_description.options, [])

    async def async_select_option(self, option: str) -> None:
        """Change to the selected entity option."""
        if not (
            await self.async_send_api_call(option, self.entity_description.command)
        ):
            raise HomeAssistantError(f"Failed to set {self.entity_description.name}")

        await self.coordinator.async_request_refresh()
