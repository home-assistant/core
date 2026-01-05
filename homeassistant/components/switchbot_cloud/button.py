"""Support for the Switchbot Bot as a Button."""

from typing import Any

from switchbot_api import BotCommands, Device, Remote, SwitchBotAPI

from homeassistant.components.button import ButtonEntity
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
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.buttons
    )


# ART_FRAME_NEXT_BUTTON_DESCRIPTION = ButtonEntityDescription(
#     key="NEXT",
#     translation_key="art_frame_next_picture",
# )
#
# ART_FRAME_PREVIOUS_BUTTON_DESCRIPTION = ButtonEntityDescription(
#     key="PREVIOUS",
#     translation_key="art_frame_previous_picture",
# )
#
#
# ART_FRAME_DESCRIPTION_SET = [ART_FRAME_NEXT_BUTTON_DESCRIPTION, ART_FRAME_PREVIOUS_BUTTON_DESCRIPTION]
#
#
# class SwitchBotCloudAiArtFrame(SwitchBotCloudEntity, ButtonEntity):
#     """Representation of a SwitchBot Ai Art Frame."""
#
#     entity_description: ButtonEntityDescription
#
#     def __init__(
#         self,
#         api: SwitchBotAPI,
#         device: Device,
#         coordinator: SwitchBotCoordinator,
#         description: ButtonEntityDescription,
#     ) -> None:
#         """Initialize SwitchBot Cloud sensor entity."""
#         super().__init__(api, device, coordinator)
#         self.entity_description = description
#         self._attr_unique_id = f"{device.device_id}_{description.key}"
#
#     # def _set_attributes(self) -> None:
#     #     """Set attributes from coordinator data."""
#     #     if not self.coordinator.data:
#     #         return
#     #     value = self.coordinator.data.get(self.entity_description.key)
#


class SwitchBotCloudBot(SwitchBotCloudEntity, ButtonEntity):
    """Representation of a SwitchBot Bot."""

    _attr_name = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

    async def async_press(self, **kwargs: Any) -> None:
        """Bot press command."""
        await self.send_api_command(BotCommands.PRESS)


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudBot:
    """Make a SwitchBotCloud button entity."""
    if device.device_type == "Bot":
        return SwitchBotCloudBot(api, device, coordinator)

    raise NotImplementedError(device.device_type)
