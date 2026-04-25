"""Support for Neato buttons."""

from __future__ import annotations

from pybotvac import Robot

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeatoConfigEntry
from .entity import NeatoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Neato button from config entry."""
    entities = [NeatoDismissAlertButton(robot) for robot in entry.runtime_data.robots]

    async_add_entities(entities, True)


class NeatoDismissAlertButton(NeatoEntity, ButtonEntity):
    """Representation of a dismiss_alert button entity."""

    _attr_translation_key = "dismiss_alert"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        robot: Robot,
    ) -> None:
        """Initialize a dismiss_alert Neato button entity."""
        super().__init__(robot)
        self._attr_unique_id = f"{robot.serial}_dismiss_alert"

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(self.robot.dismiss_current_alert)
