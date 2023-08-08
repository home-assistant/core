"""Support for Neato buttons."""
from __future__ import annotations

from pybotvac import Robot

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NEATO_DOMAIN, NEATO_ROBOTS
from .entity import NeatoEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Neato button from config entry."""
    entities = [NeatoDismissAlertButton(robot) for robot in hass.data[NEATO_ROBOTS]]

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
        self._attr_device_info = DeviceInfo(
            identifiers={(NEATO_DOMAIN, robot.serial)},
            name=robot.name,
        )

    async def async_press(self) -> None:
        """Press the button."""
        await self.hass.async_add_executor_job(self.robot.dismiss_current_alert)
