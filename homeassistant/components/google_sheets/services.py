"""Support for Google Sheets."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from gspread import Client
from gspread.exceptions import APIError
from gspread.utils import ValueInputOption
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import DOMAIN

if TYPE_CHECKING:
    from . import GoogleSheetsConfigEntry

DATA = "data"
DATA_CONFIG_ENTRY = "config_entry"
WORKSHEET = "worksheet"

SERVICE_APPEND_SHEET = "append_sheet"

SHEET_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(DATA_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(WORKSHEET): cv.string,
        vol.Required(DATA): vol.Any(cv.ensure_list, [dict]),
    },
)


def _append_to_sheet(call: ServiceCall, entry: GoogleSheetsConfigEntry) -> None:
    """Run append in the executor."""
    service = Client(Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]))  # type: ignore[no-untyped-call]
    try:
        sheet = service.open_by_key(entry.unique_id)
    except RefreshError:
        entry.async_start_reauth(call.hass)
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


async def _async_append_to_sheet(call: ServiceCall) -> None:
    """Append new line of data to a Google Sheets document."""
    entry: GoogleSheetsConfigEntry | None = call.hass.config_entries.async_get_entry(
        call.data[DATA_CONFIG_ENTRY]
    )
    if not entry or not hasattr(entry, "runtime_data"):
        raise ValueError(f"Invalid config entry: {call.data[DATA_CONFIG_ENTRY]}")
    await entry.runtime_data.async_ensure_token_valid()
    await call.hass.async_add_executor_job(_append_to_sheet, call, entry)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Add the services for Google Sheets."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPEND_SHEET,
        _async_append_to_sheet,
        schema=SHEET_SERVICE_SCHEMA,
    )
