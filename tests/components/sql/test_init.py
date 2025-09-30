"""Test for SQL component Init."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.recorder import CONF_DB_URL, Recorder
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.sql.const import (
    CONF_ADVANCED_OPTIONS,
    CONF_COLUMN_NAME,
    CONF_QUERY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import YAML_CONFIG_INVALID, YAML_CONFIG_NO_DB, init_integration

from tests.common import MockConfigEntry


async def test_setup_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test unload an entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_config(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup from yaml config."""
    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        assert await async_setup_component(hass, DOMAIN, YAML_CONFIG_NO_DB)
        await hass.async_block_till_done()


async def test_setup_invalid_config(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test setup from yaml with invalid config."""
    with patch(
        "homeassistant.components.sql.config_flow.sqlalchemy.create_engine",
    ):
        assert not await async_setup_component(hass, DOMAIN, YAML_CONFIG_INVALID)
        await hass.async_block_till_done()


async def test_migration_from_future(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test migration from future version fails."""
    config_entry = MockConfigEntry(
        title="Test future",
        domain=DOMAIN,
        source=SOURCE_USER,
        data={},
        options={
            CONF_QUERY: "SELECT 5.01 as value",
            CONF_COLUMN_NAME: "value",
            CONF_ADVANCED_OPTIONS: {},
        },
        entry_id="1",
        version=3,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_migration_from_v1_to_v2(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test migration from version 1 to 2."""
    config_entry = MockConfigEntry(
        title="Test migration",
        domain=DOMAIN,
        source=SOURCE_USER,
        data={},
        options={
            CONF_DB_URL: "sqlite://",
            CONF_NAME: "Test migration",
            CONF_QUERY: "SELECT 5.01 as value",
            CONF_COLUMN_NAME: "value",
            CONF_VALUE_TEMPLATE: "{{ value | int }}",
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
        entry_id="1",
        version=1,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert config_entry.data == {}
    assert config_entry.options == {
        CONF_QUERY: "SELECT 5.01 as value",
        CONF_COLUMN_NAME: "value",
        CONF_ADVANCED_OPTIONS: {
            CONF_VALUE_TEMPLATE: "{{ value | int }}",
            CONF_UNIT_OF_MEASUREMENT: "MiB",
            CONF_DEVICE_CLASS: SensorDeviceClass.DATA_SIZE,
            CONF_STATE_CLASS: SensorStateClass.MEASUREMENT,
        },
    }

    state = hass.states.get("sensor.test_migration")
    assert state.state == "5"
