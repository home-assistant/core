"""Support for the Switchbot Bot as a Button."""

from dataclasses import dataclass
from typing import Any

from switchbot_api import (
    Commands as SwitchBotCloudBaseCommands,
    Device,
    Remote,
    SwitchBotAPI,
)
from switchbot_api.commands import ArtFrameCommands, BotCommands, CommonCommands

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


@dataclass(frozen=True, kw_only=True)
class SwitchbotCloudButtonEntityDescription(ButtonEntityDescription):
    """Switchbot Cloud Button EntityDescription."""

    command: SwitchBotCloudBaseCommands = CommonCommands.PRESS
    command_type: str = "command"
    parameters: dict | str = "default"


BOT_BUTTON_DESCRIPTION = SwitchbotCloudButtonEntityDescription(
    key="Button", command=BotCommands.PRESS, name=None
)

ART_FRAME_NEXT_BUTTON_DESCRIPTION = SwitchbotCloudButtonEntityDescription(
    key="next",
    translation_key="art_frame_next_picture",
    command=ArtFrameCommands.NEXT,
)

ART_FRAME_PREVIOUS_BUTTON_DESCRIPTION = SwitchbotCloudButtonEntityDescription(
    key="previous",
    translation_key="art_frame_previous_picture",
    command=ArtFrameCommands.PREVIOUS,
)


BUTTON_DESCRIPTIONS_BY_DEVICE_TYPES = {
    "Bot": (BOT_BUTTON_DESCRIPTION,),
    "AI Art Frame": (
        ART_FRAME_NEXT_BUTTON_DESCRIPTION,
        ART_FRAME_PREVIOUS_BUTTON_DESCRIPTION,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    entities: list[SwitchBotCloudBot] = []
    for device, coordinator in data.devices.buttons:
        description_set = BUTTON_DESCRIPTIONS_BY_DEVICE_TYPES[device.device_type]
        for description in description_set:
            entities.extend(
                [_async_make_entity(data.api, device, coordinator, description)]
            )
    async_add_entities(entities)


class SwitchBotCloudBot(SwitchBotCloudEntity, ButtonEntity):
    """Representation of a SwitchBot Bot."""

    entity_description: SwitchbotCloudButtonEntityDescription

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device,
        coordinator: SwitchBotCoordinator,
        description: SwitchbotCloudButtonEntityDescription,
    ) -> None:
        """Initialize SwitchBot Cloud Button entity."""

        super().__init__(api, device, coordinator)
        self.entity_description = description
        if description.key != "Button":
            self._attr_unique_id = f"{device.device_id}-{description.key}"
        self._device_id = device.device_id

    async def async_press(self, **kwargs: Any) -> None:
        """Button press command."""
        await self._api.send_command(
            self._device_id,
            self.entity_description.command.value,
            self.entity_description.command_type,
            self.entity_description.parameters,
        )


@callback
def _async_make_entity(
    api: SwitchBotAPI,
    device: Device | Remote,
    coordinator: SwitchBotCoordinator,
    description: SwitchbotCloudButtonEntityDescription,
) -> SwitchBotCloudBot:
    """Make a button entity."""
    return SwitchBotCloudBot(api, device, coordinator, description)
