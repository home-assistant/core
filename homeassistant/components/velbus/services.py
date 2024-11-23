"""Support for Velbus devices."""

from __future__ import annotations

from contextlib import suppress
import logging
import os
import shutil

import voluptuous as vol

from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR

from .const import (
    CONF_INTERFACE,
    CONF_MEMO_TEXT,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
    SERVICE_SCAN,
    SERVICE_SET_MEMO_TEXT,
    SERVICE_SYNC,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


def cleanup_services(hass: HomeAssistant) -> None:
    """Unregister the velbus services."""
    hass.services.async_remove(DOMAIN, SERVICE_SCAN)
    hass.services.async_remove(DOMAIN, SERVICE_SYNC)
    hass.services.async_remove(DOMAIN, SERVICE_SET_MEMO_TEXT)
    hass.services.async_remove(DOMAIN, SERVICE_CLEAR_CACHE)


def setup_services(hass: HomeAssistant) -> None:
    """Register the velbus services."""

    def check_entry_id(interface: str) -> str:
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if "port" in config_entry.data and config_entry.data["port"] == interface:
                return config_entry.entry_id
        raise vol.Invalid(
            "The interface provided is not defined as a port in a Velbus integration"
        )

    async def scan(call: ServiceCall) -> None:
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].scan()

    async def syn_clock(call: ServiceCall) -> None:
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].sync_clock()

    async def set_memo_text(call: ServiceCall) -> None:
        """Handle Memo Text service call."""
        memo_text = call.data[CONF_MEMO_TEXT]
        await (
            hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"]
            .get_module(call.data[CONF_ADDRESS])
            .set_memo_text(memo_text.async_render())
        )

    async def clear_cache(call: ServiceCall) -> None:
        """Handle a clear cache service call."""
        # clear the cache
        with suppress(FileNotFoundError):
            if call.data.get(CONF_ADDRESS):
                await hass.async_add_executor_job(
                    os.unlink,
                    hass.config.path(
                        STORAGE_DIR,
                        f"velbuscache-{call.data[CONF_INTERFACE]}/{call.data[CONF_ADDRESS]}.p",
                    ),
                )
            else:
                await hass.async_add_executor_job(
                    shutil.rmtree,
                    hass.config.path(
                        STORAGE_DIR, f"velbuscache-{call.data[CONF_INTERFACE]}/"
                    ),
                )
        # call a scan to repopulate
        await scan(call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN,
        scan,
        vol.Schema({vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id)}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC,
        syn_clock,
        vol.Schema({vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id)}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MEMO_TEXT,
        set_memo_text,
        vol.Schema(
            {
                vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                vol.Required(CONF_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
                vol.Optional(CONF_MEMO_TEXT, default=""): cv.template,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        clear_cache,
        vol.Schema(
            {
                vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                vol.Optional(CONF_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
            }
        ),
    )
