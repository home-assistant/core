"""Support for Google Sheets."""
from __future__ import annotations

from datetime import datetime
from typing import cast

import aiohttp
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from gspread import Client
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import CONF_SHEETS_ACCESS, DATA_CONFIG_ENTRY, DOMAIN, FeatureAccess

DATA = "data"
WORKSHEET = "worksheet"

SERVICE_APPEND_SHEET = "append_sheet"

SHEET_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(DATA_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Optional(WORKSHEET): cv.string,
        vol.Required(DATA): dict,
    },
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Sheets from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    if not async_entry_has_scopes(entry):
        raise ConfigEntryAuthFailed("Required scopes are not present, reauth required")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = session

    await async_setup_service(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


def get_feature_access(config_entry: ConfigEntry) -> list[str]:
    """Return the desired sheets feature access."""
    return [
        FeatureAccess.file.value,
        FeatureAccess[config_entry.options[CONF_SHEETS_ACCESS]].value,
    ]


def async_entry_has_scopes(entry: ConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    return all(
        feature in entry.data[CONF_TOKEN]["scope"].split(" ")
        for feature in get_feature_access(entry)
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry if the access options change."""
    if not async_entry_has_scopes(entry):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_service(hass: HomeAssistant) -> None:
    """Add the services for Google Sheets."""

    def _append_to_sheet(call: ServiceCall, entry: ConfigEntry) -> None:
        """Run append in the executor."""
        service = Client(Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]))
        try:
            sheet = service.open_by_key(entry.unique_id)
        except RefreshError as ex:
            entry.async_start_reauth(hass)
            raise ex
        worksheet = sheet.worksheet(call.data.get(WORKSHEET, sheet.sheet1.title))
        row_data = {"created": str(datetime.now())} | call.data[DATA]
        columns: list[str] = next(iter(worksheet.get_values("A1:ZZ1")), [])
        row = [row_data.get(column, "") for column in columns]
        for key, value in row_data.items():
            if key not in columns:
                columns.append(key)
                worksheet.update_cell(1, len(columns), key)
                row.append(value)
        worksheet.append_row(row)

    async def append_to_sheet(call: ServiceCall) -> None:
        """Append new line of data to a Google Sheets document."""

        entry = cast(
            ConfigEntry,
            hass.config_entries.async_get_entry(call.data[DATA_CONFIG_ENTRY]),
        )
        session: OAuth2Session = hass.data[DOMAIN][entry.entry_id]
        await session.async_ensure_token_valid()
        await hass.async_add_executor_job(_append_to_sheet, call, entry)

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPEND_SHEET,
        append_to_sheet,
        schema=SHEET_SERVICE_SCHEMA,
    )
