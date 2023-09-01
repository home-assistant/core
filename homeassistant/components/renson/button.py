"""Sensor data of the Renson ventilation unit."""
from __future__ import annotations

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
    has_entity_name=True,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson sensor platform."""

    data: RensonData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [RensonButton(SYNC_TIME_BUTTON, data.api, data.coordinator, hass)]

    async_add_entities(entities)


class RensonButton(RensonEntity, ButtonEntity):
    """Get a sensor data from the Renson API and store it in the state of the class."""

    def __init__(
        self,
        description: ButtonEntityDescription,
        api: RensonVentilation,
        coordinator: RensonCoordinator,
        hass: HomeAssistant,
    ) -> None:
        """Initialize class."""
        super().__init__(description.key, api, coordinator)

        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the sync."""
        await self.hass.async_add_executor_job(self.api.sync_time)
