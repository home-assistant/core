"""Support for the Switchbot Image."""

import datetime

from switchbot_api import Device, Remote, SwitchBotAPI
from switchbot_api.utils import get_file_stream_from_cloud

from homeassistant.components.image import ImageEntity
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
        for device, coordinator in data.devices.images
    )


class SwitchBotCloudImage(SwitchBotCloudEntity, ImageEntity):
    """Base Class for SwitchBot Image."""

    _attr_translation_key = "display"

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Initialize the image entity."""
        super().__init__(api, device, coordinator)
        ImageEntity.__init__(self, self.coordinator.hass)
        self._image_content = b""

    async def async_image(self) -> bytes | None:
        """Async image."""
        if (
            not isinstance(self._attr_image_url, str)
            or len(self._attr_image_url.strip()) == 0
        ):
            self._image_content = b""
            return None
        self._image_content = await get_file_stream_from_cloud(self._attr_image_url, 5)
        return self._image_content

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        self._attr_image_last_updated = datetime.datetime.now()
        self._attr_image_url = self.coordinator.data.get("imageUrl")


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudImage:
    """Make a SwitchBotCloudImage."""
    return SwitchBotCloudImage(api, device, coordinator)
