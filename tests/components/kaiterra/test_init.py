"""Tests for Kaiterra initialization."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import (
    API_KEY,
    DEVICE_ID,
    DEVICE_ID_2,
    DEVICE_NAME,
    DEVICE_NAME_2,
    DEVICE_TYPE,
    DEVICE_TYPE_2,
    add_device_subentry,
)


async def test_yaml_setup_triggers_import_flow(
    hass: HomeAssistant,
    mock_validate_device,
    mock_latest_sensor_readings,
) -> None:
    """Test YAML setup imports into a config entry."""
    assert await async_setup_component(
        hass,
        "kaiterra",
        {
            "kaiterra": {
                CONF_API_KEY: API_KEY,
                "devices": [
                    {
                        CONF_DEVICE_ID: DEVICE_ID,
                        CONF_TYPE: DEVICE_TYPE,
                        CONF_NAME: DEVICE_NAME,
                    },
                    {
                        CONF_DEVICE_ID: DEVICE_ID_2,
                        CONF_TYPE: DEVICE_TYPE_2,
                        CONF_NAME: DEVICE_NAME_2,
                    },
                ],
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries("kaiterra")
    assert len(entries) == 1
    assert entries[0].data == {CONF_API_KEY: API_KEY}
    assert len(entries[0].subentries) == 2


async def test_setup_entry_creates_legacy_entities_from_subentries(
    hass: HomeAssistant,
    mock_config_entry,
    mock_validate_device,
    mock_latest_sensor_readings,
) -> None:
    """Test configured device subentries create the legacy entities."""
    add_device_subentry(hass, mock_config_entry)
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.office_temperature") is not None
    assert hass.states.get("sensor.office_humidity") is not None
    assert hass.states.get("air_quality.office_air_quality") is not None
    assert hass.states.get("sensor.office_temperature").attributes[
        "unit_of_measurement"
    ] in ("°C", "°F", "K")
    assert (
        hass.states.get("air_quality.office_air_quality").attributes[
            "air_quality_index_level"
        ]
        == "Moderate"
    )


async def test_setup_entry_without_devices_loads_cleanly(
    hass: HomeAssistant,
    mock_config_entry,
    mock_latest_sensor_readings,
) -> None:
    """Test a parent entry without device subentries still loads."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_entity_ids("sensor") == []
    assert hass.states.async_entity_ids("air_quality") == []


async def test_setup_entry_auth_failure_sets_setup_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_validate_device_auth_error,
    mock_latest_sensor_readings,
) -> None:
    """Test auth failures during setup fail the config entry."""
    add_device_subentry(hass, mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
