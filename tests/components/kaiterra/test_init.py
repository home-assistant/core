"""Tests for the Kaiterra integration setup."""

from __future__ import annotations

from homeassistant.components.kaiterra.const import DOMAIN, MANUFACTURER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import DEVICE_ID, DEVICE_ID_2, DEVICE_NAME


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
    assert hass.states.get("sensor.office_aqi").attributes["air_quality_index_level"] == (
        "Moderate"
    )
    assert hass.states.get("sensor.office_aqi").attributes[
        "air_quality_index_pollutant"
    ] == "TVOC"
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

    assert mock_config_entry.minor_version == 2
    assert entity_registry.async_get(old_entry.entity_id) is None
    assert entity_registry.async_get("sensor.office_aqi") is not None
