"""Example Load Platform integration."""

import asyncio
import logging

from aioketraapi import GroupStateChange, HubReady, WebsocketV2Notification
from aioketraapi.n4_hub import N4Hub

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_INSTALLATION_ID = '__installation_id__'

async def async_setup(hass, config):
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Ketra platforms from config entry"""

    installation_ids = entry.data.get("installation_ids")
    oauth_token = entry.data.get(CONF_ACCESS_TOKEN)

    hubs = []
    for installation_id in installation_ids:
        hub = await N4Hub.get_hub(installation_id, oauth_token, loop=hass.loop)
        _LOGGER.info(
            f"Discovered N4 Hub at endpoint '{hub.url_base}' for installation '{installation_id}'"
        )
        setattr(hub, ATTR_INSTALLATION_ID, installation_id)
        hubs.append(hub)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = {"hubs": hubs}

    for platform in ["light", "scene"]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class KetraPlatform:
    def __init__(self, hass, add_entities, hub, logger):
        self.hass = hass
        self.hub = hub
        self.add_entities = add_entities
        self.logger = logger
        self.ws_task = None

    async def setup_platform(self):
        # to be implemented by derived class
        self.ws_task = self.hass.loop.create_task(self.register_websocket_callback())

    async def reload_platform(self):
        # to be implemented by derived class
        pass

    async def register_websocket_callback(self):
        while True:
            await self.hub.register_websocket_callback(self.websocket_notification)
            if self.hass.is_stopping:
                break
            self.logger.warning(
                f"Websocket disconnected!  Attempting reconnection..."
            )
            await asyncio.sleep(5)

            self.hub = await N4Hub.get_hub(
                getattr(self.hub, ATTR_INSTALLATION_ID),
                self.hub.oauth_token,
                loop=self.hass.loop,
            )

    async def websocket_notification(self, notification_model):
        if isinstance(notification_model, HubReady):
            self.logger.warning(
                f"HubReady notification!  Reloading Platform"
            )
            await self.reload_platform()
            self.logger.info("Platform reload complete")
