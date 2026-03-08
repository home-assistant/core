"""Tests for the Kaiterra integration setup."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kaiterra import async_migrate_entry
from homeassistant.components.kaiterra.api_data import KaiterraApiError
from homeassistant.components.kaiterra.const import DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import API_KEY, DEVICE_ID, DEVICE_ID_2, DEVICE_NAME

from tests.common import MockConfigEntry


async def test_load_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry,
    mock_kaiterra_device_data,
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_registers_all_entities_under_one_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry,
    mock_kaiterra_device_data,
) -> None:
    """Test that one configured device owns all created entities."""
    await setup_integration(hass, mock_config_entry)

    assert (
        device := device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_ID)})
    )
    assert device.name == DEVICE_NAME
    assert device.manufacturer == MANUFACTURER

    for entity_id in (
        "sensor.office_aqi",
        "sensor.office_temperature",
        "sensor.office_humidity",
        "sensor.office_pm2_5",
        "sensor.office_pm10",
        "sensor.office_co2",
        "sensor.office_tvoc",
    ):
        assert hass.states.get(entity_id) is not None
        assert (entry := entity_registry.async_get(entity_id))
        assert entry.device_id == device.id

    assert hass.states.get("air_quality.office_air_quality") is None
    assert entity_registry.async_get("air_quality.office_air_quality") is None

    assert hass.states.get("sensor.office_aqi").state == "78"
    assert hass.states.get("sensor.office_aqi").attributes[
        "air_quality_index_level"
    ] == ("Moderate")
    assert (
        hass.states.get("sensor.office_aqi").attributes["air_quality_index_pollutant"]
        == "TVOC"
    )
    assert hass.states.get("sensor.office_temperature").attributes[
        "unit_of_measurement"
    ] in ("°C", "°F", "K")


async def test_setup_registers_multiple_devices_separately(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry,
    mock_config_entry_2,
    mock_kaiterra_device_data_multiple,
) -> None:
    """Test that multiple configured devices get separate HA devices."""
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, mock_config_entry_2)

    assert (
        office_device := device_registry.async_get_device(
            identifiers={(DOMAIN, DEVICE_ID)}
        )
    )
    assert (
        bedroom_device := device_registry.async_get_device(
            identifiers={(DOMAIN, DEVICE_ID_2)}
        )
    )
    assert office_device.id != bedroom_device.id

    assert (office_temp := entity_registry.async_get("sensor.office_temperature"))
    assert (bedroom_temp := entity_registry.async_get("sensor.bedroom_temperature"))
    assert (office_aqi := entity_registry.async_get("sensor.office_aqi"))
    assert (bedroom_aqi := entity_registry.async_get("sensor.bedroom_aqi"))

    assert office_temp.device_id == office_device.id
    assert office_aqi.device_id == office_device.id
    assert bedroom_temp.device_id == bedroom_device.id
    assert bedroom_aqi.device_id == bedroom_device.id


async def test_setup_handles_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry,
    mock_kaiterra_auth_error,
) -> None:
    """Test setup failure on invalid authentication."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_handles_connection_failure(
    hass: HomeAssistant,
    mock_config_entry,
    mock_kaiterra_api_error,
) -> None:
    """Test setup retry on connection failure."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_handles_missing_device(
    hass: HomeAssistant,
    mock_config_entry,
    mock_kaiterra_device_not_found,
) -> None:
    """Test setup failure when the configured device does not exist."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_entities_become_unavailable_and_log_once_on_api_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry,
    mock_kaiterra_device_data,
) -> None:
    """Test transient API failures mark entities unavailable and log once."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    caplog.set_level(logging.INFO)

    with patch.object(
        coordinator.api,
        "async_get_latest_sensor_readings",
        new=AsyncMock(side_effect=KaiterraApiError("offline")),
    ):
        await coordinator.async_refresh()
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.office_aqi").state == "unavailable"
    assert [
        record.message for record in caplog.records if "unavailable" in record.message
    ] == ["Device Office is unavailable: offline"]

    caplog.clear()

    with patch.object(
        coordinator.api,
        "async_get_latest_sensor_readings",
        new=AsyncMock(return_value=mock_kaiterra_device_data.return_value),
    ):
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.office_aqi").state == "78"
    assert [record.message for record in caplog.records] == [
        "Fetching Office data recovered"
    ]


async def test_migrate_entry_removes_legacy_air_quality_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry,
    mock_kaiterra_device_data,
) -> None:
    """Test migration removes the legacy air quality entity."""
    mock_config_entry.add_to_hass(hass)
    old_entry = entity_registry.async_get_or_create(
        "air_quality",
        DOMAIN,
        f"{DEVICE_ID}_air_quality",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.minor_version == 3
    assert entity_registry.async_get(old_entry.entity_id) is None
    assert entity_registry.async_get("sensor.office_aqi") is not None


async def test_migrate_entry_rejects_unknown_major_version(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test migration rejects unsupported future major versions."""
    future_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEVICE_NAME,
        unique_id=DEVICE_ID,
        data={
            CONF_API_KEY: API_KEY,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_NAME: DEVICE_NAME,
        },
        version=2,
    )
    future_entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, future_entry) is False


async def test_migrate_entry_adopts_legacy_sensor_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_kaiterra_device_data,
) -> None:
    """Test migration adopts legacy temperature and humidity entities."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEVICE_NAME,
        unique_id=DEVICE_ID,
        data={
            CONF_API_KEY: API_KEY,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_NAME: DEVICE_NAME,
        },
        minor_version=2,
    )
    mock_config_entry.add_to_hass(hass)

    legacy_temperature = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DEVICE_ID}_temperature",
        suggested_object_id="office_temperature",
        config_entry=None,
    )
    legacy_humidity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DEVICE_ID}_humidity",
        suggested_object_id="office_humidity",
        config_entry=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.minor_version == 3

    migrated_temperature = entity_registry.async_get(legacy_temperature.entity_id)
    assert migrated_temperature
    assert migrated_temperature.unique_id == f"{DEVICE_ID}_rtemp"
    assert migrated_temperature.config_entry_id == mock_config_entry.entry_id

    migrated_humidity = entity_registry.async_get(legacy_humidity.entity_id)
    assert migrated_humidity
    assert migrated_humidity.unique_id == f"{DEVICE_ID}_rhumid"
    assert migrated_humidity.config_entry_id == mock_config_entry.entry_id

    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, f"{DEVICE_ID}_rtemp")
        == legacy_temperature.entity_id
    )
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, f"{DEVICE_ID}_rhumid")
        == legacy_humidity.entity_id
    )


async def test_migrate_entry_prefers_legacy_sensor_entity_over_duplicate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_kaiterra_device_data,
) -> None:
    """Test migration keeps the legacy entity ID when a duplicate already exists."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEVICE_NAME,
        unique_id=DEVICE_ID,
        data={
            CONF_API_KEY: API_KEY,
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_NAME: DEVICE_NAME,
        },
        minor_version=2,
    )
    mock_config_entry.add_to_hass(hass)

    legacy_temperature = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DEVICE_ID}_temperature",
        suggested_object_id="office_temperature",
        config_entry=None,
    )
    duplicate_temperature = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{DEVICE_ID}_rtemp",
        suggested_object_id="office_temperature_2",
        config_entry=mock_config_entry,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_temperature = entity_registry.async_get(legacy_temperature.entity_id)
    assert migrated_temperature
    assert migrated_temperature.unique_id == f"{DEVICE_ID}_rtemp"
    assert migrated_temperature.config_entry_id == mock_config_entry.entry_id
    assert entity_registry.async_get(duplicate_temperature.entity_id) is None
