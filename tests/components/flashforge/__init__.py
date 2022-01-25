"""Tests for the Flashforge integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.flashforge.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
