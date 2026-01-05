"""Support for the Switchbot Bot as a Button."""

from typing import Any

from switchbot_api import BotCommands, Device, Remote, SwitchBotAPI
from switchbot_api.commands import ArtFrameCommands

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    entities: list[SwitchBotCloudBot] = []
    for device, coordinator in data.devices.buttons:
        description_set = BUTTON_DESCRIPTIONS_BY_DEVICE_TYPES.get(device.device_type)
        if description_set is None:
            entities.extend([_async_make_entity(data.api, device, coordinator)])
        else:
            for description in description_set:
                entities.extend(
                    [_async_make_entity(data.api, device, coordinator, description)]
                )

    async_add_entities(entities)


ART_FRAME_NEXT_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="Next",
    translation_key="art_frame_next_picture",
    entity_registry_enabled_default=False,
)

ART_FRAME_PREVIOUS_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="Previous",
    translation_key="art_frame_previous_picture",
    entity_registry_enabled_default=False,
)


BUTTON_DESCRIPTIONS_BY_DEVICE_TYPES = {
    "AI Art Frame": (
        ART_FRAME_NEXT_BUTTON_DESCRIPTION,
        ART_FRAME_PREVIOUS_BUTTON_DESCRIPTION,
    ),
}


class SwitchBotCloudBot(SwitchBotCloudEntity, ButtonEntity):
    """Representation of a SwitchBot Bot."""

    _attr_name: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

    async def async_press(self, **kwargs: Any) -> None:
        """Bot press command."""
        await self.send_api_command(BotCommands.PRESS)


class SwitchBotCloudAiArtFrame(SwitchBotCloudBot):
    """Representation of a SwitchBot Ai Art Frame."""

    _attr_has_entity_name = True
    entity_description: ButtonEntityDescription

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device,
        coordinator: SwitchBotCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize SwitchBot Cloud sensor entity."""

        super().__init__(api, device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}-{description.key}"
        self._device_id = device.device_id
        self._attr_name = description.key or "Button"

    async def async_press(self, **kwargs: Any) -> None:
        """Button press command."""
        if self.entity_description.key == ART_FRAME_NEXT_BUTTON_DESCRIPTION.key:
            await self._api.send_command(
                self._device_id, command=ArtFrameCommands.NEXT.value
            )
        else:
            await self._api.send_command(
                self._device_id, command=ArtFrameCommands.PREVIOUS.value
            )


@callback
def _async_make_entity(
    api: SwitchBotAPI,
    device: Device | Remote,
    coordinator: SwitchBotCoordinator,
    description: ButtonEntityDescription | None = None,
) -> SwitchBotCloudBot:
    """Make a button entity."""
    if device.device_type == "AI Art Frame":
        assert description is not None
        return SwitchBotCloudAiArtFrame(api, device, coordinator, description)
    return SwitchBotCloudBot(api, device, coordinator)
