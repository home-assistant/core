"""Sensor data of the Renson ventilation unit."""
from __future__ import annotations

from _collections_abc import Callable
from renson_endura_delta.renson import RensonVentilation

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RensonCoordinator, RensonData
from .const import DOMAIN
from .entity import RensonEntity

SYNC_TIME_BUTTON: ButtonEntityDescription = ButtonEntityDescription(
    key="sync_time",
    device_class=ButtonDeviceClass.UPDATE,
    entity_category=EntityCategory.CONFIG,
    translation_key="sync_time",
)

RESTART_BUTTON: ButtonEntityDescription = ButtonEntityDescription(
    key="restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
    translation_key="restart",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson button platform."""

    data: RensonData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        RensonButton(
            SYNC_TIME_BUTTON, data.api, data.coordinator, hass, data.api.sync_time
        ),
        RensonButton(
            RESTART_BUTTON, data.api, data.coordinator, hass, data.api.restart_device
        ),
    ]

    async_add_entities(entities)


class RensonButton(RensonEntity, ButtonEntity):
    """Representation of a Renson actions."""

    _attr_has_entity_name = True

    def __init__(
        self,
        description: ButtonEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
        hass: HomeAssistant,
        action: Callable,
    ) -> None:
        """Initialize class."""
        super().__init__(description.key, api, coordinator)

        self.entity_description = description
        self.action = action

    async def async_press(self) -> None:
        """Triggers the action."""
        await self.hass.async_add_executor_job(self.action)
        await self.coordinator.async_request_refresh()
