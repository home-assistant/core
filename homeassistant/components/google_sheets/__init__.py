"""Support for Google Sheets."""

from __future__ import annotations

from datetime import datetime

import aiohttp
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from gspread import Client
from gspread.exceptions import APIError
from gspread.utils import ValueInputOption
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DEFAULT_ACCESS, DOMAIN

type GoogleSheetsConfigEntry = ConfigEntry[OAuth2Session]

DATA = "data"
DATA_CONFIG_ENTRY = "config_entry"
WORKSHEET = "worksheet"

SERVICE_APPEND_SHEET = "append_sheet"

SHEET_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(DATA_CONFIG_ENTRY): ConfigEntrySelector(),
        vol.Optional(WORKSHEET): cv.string,
        vol.Required(DATA): vol.Any(cv.ensure_list, [dict]),
    },
)


async def async_setup_entry(
    hass: HomeAssistant, entry: GoogleSheetsConfigEntry
) -> bool:
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

    if not async_entry_has_scopes(hass, entry):
        raise ConfigEntryAuthFailed("Required scopes are not present, reauth required")
    entry.runtime_data = session

    await async_setup_service(hass)

    return True


def async_entry_has_scopes(hass: HomeAssistant, entry: GoogleSheetsConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    return DEFAULT_ACCESS in entry.data.get(CONF_TOKEN, {}).get("scope", "").split(" ")


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleSheetsConfigEntry
) -> bool:
    """Unload a config entry."""
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        for service_name in hass.services.async_services_for_domain(DOMAIN):
            hass.services.async_remove(DOMAIN, service_name)

    return True


async def async_setup_service(hass: HomeAssistant) -> None:
    """Add the services for Google Sheets."""

    def _append_to_sheet(call: ServiceCall, entry: GoogleSheetsConfigEntry) -> None:
        """Run append in the executor."""
        service = Client(Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]))  # type: ignore[no-untyped-call]
        try:
            sheet = service.open_by_key(entry.unique_id)
        except RefreshError:
            entry.async_start_reauth(hass)
            raise
        except APIError as ex:
            raise HomeAssistantError("Failed to write data") from ex

        worksheet = sheet.worksheet(call.data.get(WORKSHEET, sheet.sheet1.title))
        columns: list[str] = next(iter(worksheet.get_values("A1:ZZ1")), [])
        now = str(datetime.now())
        rows = []
        for d in call.data[DATA]:
            row_data = {"created": now} | d
            row = [row_data.get(column, "") for column in columns]
            for key, value in row_data.items():
                if key not in columns:
                    columns.append(key)
                    worksheet.update_cell(1, len(columns), key)
                    row.append(value)
            rows.append(row)
        worksheet.append_rows(rows, value_input_option=ValueInputOption.user_entered)

    async def append_to_sheet(call: ServiceCall) -> None:
        """Append new line of data to a Google Sheets document."""
        entry: GoogleSheetsConfigEntry | None = hass.config_entries.async_get_entry(
            call.data[DATA_CONFIG_ENTRY]
        )
        if not entry or not hasattr(entry, "runtime_data"):
            raise ValueError(f"Invalid config entry: {call.data[DATA_CONFIG_ENTRY]}")
        await entry.runtime_data.async_ensure_token_valid()
        await hass.async_add_executor_job(_append_to_sheet, call, entry)

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPEND_SHEET,
        append_to_sheet,
        schema=SHEET_SERVICE_SCHEMA,
    )
