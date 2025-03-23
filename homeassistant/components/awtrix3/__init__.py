"""__init__.py: AWTRIX integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging

import aiohttp
from aiohttp import web

from homeassistant.components import webhook
from homeassistant.components.notify import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import async_get_coordinator_by_device_name
from .const import DOMAIN, PLATFORMS
from .coordinator import AwtrixCoordinator
from .services import AwtrixServicesSetup

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

type MyConfigEntry = ConfigEntry[RuntimeData]

@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator
    cancel_update_listener: Callable


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Awtrix component."""

    AwtrixServicesSetup(hass, config)

    # notifications
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME:  "awtrix",
            },
            config
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Set up Awtrix Integration from a config entry."""

    coordinator = AwtrixCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data:
        raise ConfigEntryNotReady

    cancel_update_listener = config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    config_entry.runtime_data = RuntimeData(
        coordinator, cancel_update_listener)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    await register_webhook_v1(hass, config_entry)

    # notification (deprecated])
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {
                CONF_NAME:  config_entry.unique_id,
                "coordinator": coordinator,
            },
            {},
        )
    )

    # Return true to denote a successful setup.
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Delete device if selected from UI."""
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: MyConfigEntry) -> bool:
    """Unload a config entry."""

    # Unload services
    for service in hass.services.async_services_for_domain(DOMAIN):
        hass.services.async_remove(DOMAIN, service)

    # Unload platforms and return result
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

async def register_webhook_v1(hass: HomeAssistant, config_entry):
    """Register webhook V1."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook callback.

        dev.json
        button_callback: http callback url for button presses.
        Sample http://hass.local:8123/api/webhook/awtrix_7c43d4
        TODO:
            - pass awtrix uid wia body automatically
            - remove awtrix uid from url
        """
        try:
            async with asyncio.timeout(5):
                data = dict(await request.post())
        except (TimeoutError, aiohttp.web.HTTPException) as error:
            _LOGGER.error("Could not get information from POST <%s>", error)
            return None
        device_name = webhook_id
        coordinators =  async_get_coordinator_by_device_name(hass, [device_name])
        coordinator = next(iter(coordinators), None)
        if coordinator is not None:
            button = data["button"]
            state = data["state"]
            coordinator.action_press(button, state)
        return web.Response(text="OK")

    webhook.async_register(
        hass, DOMAIN, "Awtrix", config_entry.unique_id, handle_webhook
    )

async def register_webhook_v2(hass: HomeAssistant):
    """Register webhook V2."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle webhook callback.

        dev.json
        button_callback: http callback url for button presses.
        Sample http://hass.local:8123/api/webhook/awtrix
        TODO:
            - pass awtrix uid wia body automatically
            - remove awtrix uid from url
        """
        try:
            async with asyncio.timeout(5):
                data = dict(await request.post())
        except (TimeoutError, aiohttp.web.HTTPException) as error:
            _LOGGER.error("Could not get information from POST <%s>", error)
            return None

        button = data["button"]
        state = data["state"]
        uid = data.get("uid")
        if uid is not None:
            coordinators =  async_get_coordinator_by_device_name(hass, [uid])
            coordinator = next(iter(coordinators), None)
            if coordinator is not None:
                coordinator.action_press(button, state)
        return web.Response(text="OK")

    webhook.async_register(
        hass, DOMAIN, "Awtrix", "Awtrix-WebHook", handle_webhook
    )
