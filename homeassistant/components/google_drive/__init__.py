"""Support for Google Drive."""
from __future__ import annotations

from typing import cast

import aiohttp
from google.oauth2.credentials import Credentials
from gspread import Client
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.config_validation as cv

from .const import DATA_CONFIG_ENTRY, DEFAULT_ACCESS, DOMAIN

DATA = "data"
WORKSHEET = "worksheet"

SERVICE_APPEND_SHEET = "append_sheet"

APPEND_SHEET_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(DATA_CONFIG_ENTRY): cv.string,
        vol.Optional(WORKSHEET): cv.string,
        vol.Required(DATA): list,
    },
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Drive from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            return False
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    if not async_entry_has_scopes(hass, entry):
        return False
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = session

    await async_setup_drive_service(hass)

    return True


def async_entry_has_scopes(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    return DEFAULT_ACCESS in entry.data.get(CONF_TOKEN, {}).get("scope", [])


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def async_setup_drive_service(hass: HomeAssistant) -> None:
    """Add the services for Google Sheets."""

    async def append_to_sheet(call: ServiceCall) -> None:
        """Edit Google Sheets document."""

        def _append_to_sheet() -> None:
            """Run append in the executor."""
            service = Client(Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]))
            sheet = service.open_by_key(entry.unique_id)
            worksheet = sheet.worksheet(call.data.get(WORKSHEET, sheet.sheet1.title))
            worksheet.append_row(call.data[DATA])

        entry = cast(
            ConfigEntry,
            hass.config_entries.async_get_entry(call.data[DATA_CONFIG_ENTRY]),
        )
        session: OAuth2Session = hass.data[DOMAIN][entry.entry_id]
        await session.async_ensure_token_valid()
        await hass.async_add_executor_job(_append_to_sheet)

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPEND_SHEET,
        append_to_sheet,
        schema=APPEND_SHEET_SERVICE_SCHEMA,
    )
