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
    async_add_entities(
        SwitchBotCloudBot(data.api, device, coordinator)
        for device, coordinator in data.devices.buttons
    )


class SwitchBotCloudBot(SwitchBotCloudEntity, ButtonEntity):
    """Representation of a SwitchBot Bot."""

    _attr_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

    async def async_press(self, **kwargs: Any) -> None:
        """Bot press command."""
        model_name: str | None = (
            self.device_info.get("model") if self.device_info else None
        )
        if model_name and model_name in ["Garage Door Opener"]:
            response: dict | None = await self._api.get_status(self.unique_id)
            if response is not None:
                door_status: int | None = response.get("doorStatus")
                if door_status is not None:
                    if door_status == 1:
                        await self.send_api_command(CommonCommands.ON)
                    else:
                        await self.send_api_command(CommonCommands.OFF)
        else:
            await self.send_api_command(BotCommands.PRESS)
