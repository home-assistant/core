"""Tests for the sql component."""
from typing import Any

from homeassistant.components.recorder import CONF_DB_URL
from homeassistant.components.sql.const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_QUERY: "SELECT ROUND(page_count * page_size / 1024 / 1024, 1) as size FROM pragma_page_count(), pragma_page_size();",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID = {
    CONF_DB_URL: "",
    CONF_QUERY: "UPDATE ROUND(page_count * page_size / 1024 / 1024, 1) as size FROM pragma_page_count(), pragma_page_size();",
    CONF_COLUMN_NAME: "size",
    CONF_VALUE_TEMPLATE: "{% if %}",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}


async def init_integration(
    hass: HomeAssistant,
    config: dict[str, Any] = None,
    entry_id: str = "1",
    source: str = SOURCE_USER,
) -> MockConfigEntry:
    """Set up the SQL integration in Home Assistant."""
    if not config:
        config = ENTRY_CONFIG

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data=config,
        entry_id=entry_id,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
