"""Tests for the sql component."""
from __future__ import annotations

from typing import Any

from spencerassistant.components.recorder import CONF_DB_URL
from spencerassistant.components.sql.const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN
from spencerassistant.config_entries import SOURCE_USER
from spencerassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_DB_URL: "sqlite://",
    CONF_NAME: "Get Value",
    CONF_QUERY: "SELECT 5 as value",
    CONF_COLUMN_NAME: "value",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID_QUERY = {
    CONF_DB_URL: "sqlite://",
    CONF_NAME: "Get Value",
    CONF_QUERY: "UPDATE 5 as value",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID_QUERY_OPT = {
    CONF_DB_URL: "sqlite://",
    CONF_QUERY: "UPDATE 5 as value",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_NO_RESULTS = {
    CONF_DB_URL: "sqlite://",
    CONF_NAME: "Get Value",
    CONF_QUERY: "SELECT kalle as value from no_table;",
    CONF_COLUMN_NAME: "value",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}


async def init_integration(
    hass: spencerAssistant,
    config: dict[str, Any] = None,
    entry_id: str = "1",
    source: str = SOURCE_USER,
) -> MockConfigEntry:
    """Set up the SQL integration in spencer Assistant."""
    if not config:
        config = ENTRY_CONFIG

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data={},
        options=config,
        entry_id=entry_id,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
