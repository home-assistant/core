"""Support for the Switchbot Bot as a Button."""

from typing import Any

from switchbot_api import BotCommands, CommonCommands

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    entities_list: list[SwitchBotCloudBot | SwitchBotCloudGarageDoorOpener] = []
    for device, coordinator in data.devices.buttons:
        if device.device_type in ["Garage Door Opener"]:
            entities_list.extend(
                [SwitchBotCloudGarageDoorOpener(data.api, device, coordinator)]
            )
        else:
            entities_list.extend([SwitchBotCloudBot(data.api, device, coordinator)])
    async_add_entities(entities_list)


class SwitchBotCloudBot(SwitchBotCloudEntity, ButtonEntity):
    """Representation of a SwitchBot Bot."""

    _attr_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

    async def async_press(self, **kwargs: Any) -> None:
        """Bot press command."""
        await self.send_api_command(BotCommands.PRESS)


class SwitchBotCloudGarageDoorOpener(SwitchBotCloudBot):
    """Representation of a SwitchBot GarageDoorOpener."""

    async def async_press(self, **kwargs: Any) -> None:
        """GarageDoorOpener press command."""
        response: dict | None = await self._api.get_status(self.unique_id)
        if response is not None:
            door_status: int | None = response.get("doorStatus")
            if door_status is not None:
                if door_status == 1:
                    await self.send_api_command(CommonCommands.ON)
                else:
                    await self.send_api_command(CommonCommands.OFF)
