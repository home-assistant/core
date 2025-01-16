"""Support for Velbus devices."""

from __future__ import annotations

from contextlib import suppress
import os
import shutil
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.storage import STORAGE_DIR

if TYPE_CHECKING:
    from . import VelbusConfigEntry

from .const import (
    CONF_CONFIG_ENTRY,
    CONF_INTERFACE,
    CONF_MEMO_TEXT,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
    SERVICE_SCAN,
    SERVICE_SET_MEMO_TEXT,
    SERVICE_SYNC,
)


def setup_services(hass: HomeAssistant) -> None:
    """Register the velbus services."""

    def check_entry_id(interface: str) -> str:
        """Check the config_entry for a specific interface."""
        for config_entry in hass.config_entries.async_entries(DOMAIN):
            if "port" in config_entry.data and config_entry.data["port"] == interface:
                return config_entry.entry_id
        raise vol.Invalid(
            "The interface provided is not defined as a port in a Velbus integration"
        )

    async def get_config_entry(call: ServiceCall) -> VelbusConfigEntry:
        """Get the config entry for this service call."""
        if CONF_CONFIG_ENTRY in call.data:
            entry_id = call.data[CONF_CONFIG_ENTRY]
        elif CONF_INTERFACE in call.data:
            # Deprecated in 2025.2, to remove in 2025.8
            async_create_issue(
                hass,
                DOMAIN,
                "deprecated_interface_parameter",
                breaks_in_ha_version="2025.8.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_interface_parameter",
            )
            entry_id = call.data[CONF_INTERFACE]
        if not (entry := hass.config_entries.async_get_entry(entry_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_found",
                translation_placeholders={"target": DOMAIN},
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_loaded",
                translation_placeholders={"target": entry.title},
            )
        return entry

    async def scan(call: ServiceCall) -> None:
        """Handle a scan service call."""
        entry = await get_config_entry(call)
        await entry.runtime_data.controller.scan()

    async def syn_clock(call: ServiceCall) -> None:
        """Handle a sync clock service call."""
        entry = await get_config_entry(call)
        await entry.runtime_data.controller.sync_clock()

    async def set_memo_text(call: ServiceCall) -> None:
        """Handle Memo Text service call."""
        entry = await get_config_entry(call)
        memo_text = call.data[CONF_MEMO_TEXT]
        module = entry.runtime_data.controller.get_module(call.data[CONF_ADDRESS])
        if not module:
            raise ServiceValidationError("Module not found")
        await module.set_memo_text(memo_text.async_render())

    async def clear_cache(call: ServiceCall) -> None:
        """Handle a clear cache service call."""
        entry = await get_config_entry(call)
        with suppress(FileNotFoundError):
            if call.data.get(CONF_ADDRESS):
                await hass.async_add_executor_job(
                    os.unlink,
                    hass.config.path(
                        STORAGE_DIR,
                        f"velbuscache-{entry.entry_id}/{call.data[CONF_ADDRESS]}.p",
                    ),
                )
            else:
                await hass.async_add_executor_job(
                    shutil.rmtree,
                    hass.config.path(STORAGE_DIR, f"velbuscache-{entry.entry_id}/"),
                )
        # call a scan to repopulate
        await scan(call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN,
        scan,
        vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_CONFIG_ENTRY): selector.ConfigEntrySelector(
                        {
                            "integration": DOMAIN,
                        }
                    )
                }
            ),
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC,
        syn_clock,
        vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_CONFIG_ENTRY): selector.ConfigEntrySelector(
                        {
                            "integration": DOMAIN,
                        }
                    )
                }
            ),
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MEMO_TEXT,
        set_memo_text,
        vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                    vol.Required(CONF_ADDRESS): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=255)
                    ),
                    vol.Optional(CONF_MEMO_TEXT, default=""): cv.template,
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_CONFIG_ENTRY): selector.ConfigEntrySelector(
                        {
                            "integration": DOMAIN,
                        }
                    ),
                    vol.Required(CONF_ADDRESS): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=255)
                    ),
                    vol.Optional(CONF_MEMO_TEXT, default=""): cv.template,
                }
            ),
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        clear_cache,
        vol.Any(
            vol.Schema(
                {
                    vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
                    vol.Optional(CONF_ADDRESS): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=255)
                    ),
                }
            ),
            vol.Schema(
                {
                    vol.Required(CONF_CONFIG_ENTRY): selector.ConfigEntrySelector(
                        {
                            "integration": DOMAIN,
                        }
                    ),
                    vol.Optional(CONF_ADDRESS): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=255)
                    ),
                }
            ),
        ),
    )
