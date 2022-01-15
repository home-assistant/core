"""Support for Litter-Robot button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity
from .hub import LitterRobotHub

TYPE_RESET_WASTE_DRAWER = "Reset Waste Drawer"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LitterRobotResetWasteDrawerButton(
                robot=robot, entity_type=TYPE_RESET_WASTE_DRAWER, hub=hub
            )
            for robot in hub.account.robots
        ]
    )


class LitterRobotResetWasteDrawerButton(LitterRobotEntity, ButtonEntity):
    """Litter-Robot reset waste drawer button."""

    _attr_icon = "mdi:delete-variant"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Press the button."""
        await self.robot.reset_waste_drawer()
        self.coordinator.async_set_updated_data(True)
