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

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

if TYPE_CHECKING:
    from . import GoogleSheetsConfigEntry

ADD_CREATED_COLUMN = "add_created_column"
DATA = "data"
ROWS = "rows"
SPREADSHEET_ID = "spreadsheet_id"
WORKSHEET = "worksheet"

SERVICE_APPEND_SHEET = "append_sheet"
SERVICE_GET_SHEET = "get_sheet"

APPEND_SHEET_SERVICE_SCHEMA = vol.All(
    {
        vol.Optional(SPREADSHEET_ID): cv.string,
        vol.Optional(WORKSHEET): cv.string,
        vol.Optional(ADD_CREATED_COLUMN, default=True): cv.boolean,
        vol.Required(DATA): vol.Any(cv.ensure_list, [dict]),
    },
)

GET_SHEET_SERVICE_SCHEMA = vol.All(
    {
        vol.Optional(SPREADSHEET_ID): cv.string,
        vol.Optional(WORKSHEET): cv.string,
        vol.Required(ROWS): cv.positive_int,
    },
)


def _append_to_sheet(call: ServiceCall, entry: GoogleSheetsConfigEntry) -> None:
    """Run append in the executor."""
    service = Client(Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]))  # type: ignore[no-untyped-call]
    try:
        spreadsheet = service.open_by_key(
            call.data.get(SPREADSHEET_ID, entry.unique_id)
        )
    except RefreshError:
        entry.async_start_reauth(call.hass)
        raise
    except APIError as ex:
        raise HomeAssistantError("Failed to write data") from ex

    worksheet = spreadsheet.worksheet(
        call.data.get(WORKSHEET, spreadsheet.sheet1.title)
    )
    columns: list[str] = next(iter(worksheet.get_values("A1:ZZ1")), [])
    add_created_column = call.data[ADD_CREATED_COLUMN]
    now = str(datetime.now())
    rows = []
    for d in call.data[DATA]:
        row_data = ({"created": now} | d) if add_created_column else d
        row = [row_data.get(column, "") for column in columns]
        for key, value in row_data.items():
            if key not in columns:
                columns.append(key)
                worksheet.update_cell(1, len(columns), key)
                row.append(value)
        rows.append(row)
    worksheet.append_rows(rows, value_input_option=ValueInputOption.user_entered)


def _get_from_sheet(
    call: ServiceCall, entry: GoogleSheetsConfigEntry
) -> JsonObjectType:
    """Run get in the executor."""
    service = Client(Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]))  # type: ignore[no-untyped-call]
    try:
        spreadsheet = service.open_by_key(
            call.data.get(SPREADSHEET_ID, entry.unique_id)
        )
    except RefreshError:
        entry.async_start_reauth(call.hass)
        raise
    except APIError as ex:
        raise HomeAssistantError("Failed to retrieve data") from ex

    worksheet = spreadsheet.worksheet(
        call.data.get(WORKSHEET, spreadsheet.sheet1.title)
    )
    all_values = worksheet.get_values()
    return {"range": all_values[-call.data[ROWS] :]}


def _get_config_entry(call: ServiceCall) -> GoogleSheetsConfigEntry:
    """Get the config entry for the service call."""
    entries: list[GoogleSheetsConfigEntry] = call.hass.config_entries.async_entries(
        DOMAIN
    )

    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_config_entry",
        )

    if len(entries) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_config_entries",
        )

    entry = entries[0]

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )

    return entry


async def _async_append_to_sheet(call: ServiceCall) -> None:
    """Append new line of data to a Google Sheets document."""
    entry = _get_config_entry(call)
    await entry.runtime_data.async_ensure_token_valid()
    await call.hass.async_add_executor_job(_append_to_sheet, call, entry)


async def _async_get_from_sheet(call: ServiceCall) -> ServiceResponse:
    """Get lines of data from a Google Sheets document."""
    entry = _get_config_entry(call)
    await entry.runtime_data.async_ensure_token_valid()
    return await call.hass.async_add_executor_job(_get_from_sheet, call, entry)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Add the services for Google Sheets."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPEND_SHEET,
        _async_append_to_sheet,
        schema=APPEND_SHEET_SERVICE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SHEET,
        _async_get_from_sheet,
        schema=GET_SHEET_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
