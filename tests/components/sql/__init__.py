"""Tests for the sql component."""
from __future__ import annotations

from typing import Any

from homeassistant.components.recorder import CONF_DB_URL
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sql.const import CONF_COLUMN_NAME, CONF_QUERY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_CONFIG = {
    CONF_NAME: "Get Value",
    CONF_QUERY: "SELECT 5 as value",
    CONF_COLUMN_NAME: "value",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID_QUERY = {
    CONF_NAME: "Get Value",
    CONF_QUERY: "UPDATE 5 as value",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID_QUERY_OPT = {
    CONF_QUERY: "UPDATE 5 as value",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID_COLUMN_NAME = {
    CONF_NAME: "Get Value",
    CONF_QUERY: "SELECT 5 as value",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_INVALID_COLUMN_NAME_OPT = {
    CONF_QUERY: "SELECT 5 as value",
    CONF_COLUMN_NAME: "size",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

ENTRY_CONFIG_NO_RESULTS = {
    CONF_NAME: "Get Value",
    CONF_QUERY: "SELECT kalle as value from no_table;",
    CONF_COLUMN_NAME: "value",
    CONF_UNIT_OF_MEASUREMENT: "MiB",
}

YAML_CONFIG = {
    "sql": {
        CONF_DB_URL: "sqlite://",
        CONF_NAME: "Get Value",
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_UNIT_OF_MEASUREMENT: "MiB",
        CONF_UNIQUE_ID: "unique_id_12345",
        CONF_VALUE_TEMPLATE: "{{ value }}",
        CONF_DEVICE_CLASS: SensorDeviceClass.DATA_RATE,
        CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
    }
}

YAML_CONFIG_FULL_TABLE_SCAN = {
    "sql": {
        CONF_NAME: "Get entity_id",
        CONF_QUERY: "SELECT entity_id from states",
        CONF_COLUMN_NAME: "entity_id",
        CONF_UNIQUE_ID: "entity_id_12345",
    }
}


YAML_CONFIG_FULL_TABLE_SCAN_NO_UNIQUE_ID = {
    "sql": {
        CONF_NAME: "Get entity_id",
        CONF_QUERY: "SELECT entity_id from states",
        CONF_COLUMN_NAME: "entity_id",
    }
}

YAML_CONFIG_FULL_TABLE_SCAN_WITH_MULTIPLE_COLUMNS = {
    "sql": {
        CONF_NAME: "Get entity_id",
        CONF_QUERY: "SELECT entity_id,state_id from states",
        CONF_COLUMN_NAME: "entity_id",
    }
}

YAML_CONFIG_WITH_VIEW_THAT_CONTAINS_ENTITY_ID = {
    "sql": {
        CONF_NAME: "Get entity_id",
        CONF_QUERY: "SELECT value from view_sensor_db_unique_entity_ids;",
        CONF_COLUMN_NAME: "value",
    }
}


YAML_CONFIG_BINARY = {
    "sql": {
        CONF_DB_URL: "sqlite://",
        CONF_NAME: "Get Binary Value",
        CONF_QUERY: "SELECT cast(x'd34324324230392032' as blob) as value, cast(x'd343aa' as blob) as test_attr",
        CONF_COLUMN_NAME: "value",
        CONF_UNIQUE_ID: "unique_id_12345",
    }
}

YAML_CONFIG_INVALID = {
    "sql": {
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
        CONF_UNIT_OF_MEASUREMENT: "MiB",
        CONF_UNIQUE_ID: "unique_id_12345",
    }
}

YAML_CONFIG_NO_DB = {
    "sql": {
        CONF_NAME: "Get Value",
        CONF_QUERY: "SELECT 5 as value",
        CONF_COLUMN_NAME: "value",
    }
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
        data={},
        options=config,
        entry_id=entry_id,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
