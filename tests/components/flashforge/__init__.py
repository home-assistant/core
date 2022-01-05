"""Tests for the FlashForge 3D Printer integration."""

from typing import Any
from unittest.mock import Mock

import voluptuous as vol

from homeassistant.components.flashforge.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

from .const_response import (
    MACHINE_INFO,
    PROGRESS_PRINTING,
    PROGRESS_READY,
    STATUS_PRINTING,
    STATUS_READY,
    TEMP_PRINTING,
    TEMP_READY,
)

from tests.common import MockConfigEntry


def prepare_mocked_connection(mocked_obj: Mock) -> Mock:
    """Prepare a mock for the printer."""

    mocked_obj.sendInfoRequest.return_value = MACHINE_INFO
    mocked_obj.sendStatusRequest.return_value = STATUS_READY
    mocked_obj.sendTempRequest.return_value = TEMP_READY
    mocked_obj.sendProgressRequest.return_value = PROGRESS_READY

    return mocked_obj


def change_printer_values(mocked_obj: Mock) -> Mock:
    """Change the values that the printer responds with."""

    mocked_obj.sendStatusRequest.return_value = STATUS_PRINTING
    mocked_obj.sendTempRequest.return_value = TEMP_PRINTING
    mocked_obj.sendProgressRequest.return_value = PROGRESS_PRINTING

    return mocked_obj


def get_schema_default(schema: vol.Schema, key_name: str) -> Any:
    """Return default value from a schema."""
    for schema_key in schema:
        if schema_key == key_name:
            if schema_key.default is not vol.UNDEFINED:
                return schema_key.default()
            else:
                raise AttributeError(f"{key_name} doesn't have a default.")
    raise KeyError(f"{key_name} not in schema.")


def get_schema_suggested(schema: vol.Schema, key_name: str) -> Any:
    """Return suggested value from a schema."""
    for schema_key in schema:
        if schema_key == key_name:
            if (
                isinstance(schema_key.description, dict)
                and "suggested_value" in schema_key.description
            ):
                return schema_key.description["suggested_value"]
            else:
                raise AttributeError(f"{key_name} doesn't have a suggested value.")
    raise KeyError(f"{key_name} not in schema.")


async def init_integration(
    hass: HomeAssistant, skip_setup: bool = False
) -> MockConfigEntry:
    """Set up a Flashforge printer in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SNADVA1234567",
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: 8899,
            CONF_SERIAL_NUMBER: "SNADVA1234567",
        },
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
