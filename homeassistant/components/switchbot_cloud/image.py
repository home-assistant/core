"""Support for the Switchbot Image."""

from collections import deque
import datetime

from aiohttp import ClientTimeout
from switchbot_api import Device, Remote, SwitchBotAPI

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        self.access_tokens: deque[str] = deque()
        self.access_tokens.append("switchbot_art_frame_token")
        self._image_content = b""

    async def async_image(self) -> bytes | None:
        """Async image."""
        await self.download_image()
        return self._image_content

    async def async_update(self) -> None:
        """Async update."""
        self._attr_image_last_updated = datetime.datetime.now()

    async def download_image(self) -> None:
        """Download image."""
        if not isinstance(self.image_url, str) or len(self.image_url.strip()) == 0:
            self._image_content = b""
            return
        timeout = ClientTimeout(total=30, connect=5, sock_read=20)
        session = async_get_clientsession(self.coordinator.hass)
        async with session.get(self.image_url, timeout=timeout) as response:
            response.raise_for_status()
            self._image_content = await response.read()

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
    """Make a SwitchBotCloudLight."""
    return SwitchBotCloudImage(api, device, coordinator)
