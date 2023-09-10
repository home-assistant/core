"""Test the Landis + Gyr Heat Meter init."""
from unittest.mock import patch

from homeassistant.components.landisgyr_heat_meter.const import (
    DOMAIN as LANDISGYR_HEAT_METER_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

API_HEAT_METER_SERVICE = (
    "homeassistant.components.landisgyr_heat_meter.ultraheat_api.HeatMeterService"
)


@patch(API_HEAT_METER_SERVICE)
async def test_unload_entry(_, hass: HomeAssistant) -> None:
    """Test removing config entry."""
    mock_entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "12345",
    }
    mock_entry = MockConfigEntry(
        domain="landisgyr_heat_meter",
        title="LUGCUH50",
        entry_id="987654321",
        data=mock_entry_data,
    )
    mock_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert "landisgyr_heat_meter" in hass.config.components

    assert await hass.config_entries.async_remove(mock_entry.entry_id)


@patch(API_HEAT_METER_SERVICE)
async def test_migrate_entry(_, hass: HomeAssistant) -> None:
    """Test successful migration of entry data from version 1 to 2."""

    mock_entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "12345",
    }
    mock_entry = MockConfigEntry(
        domain="landisgyr_heat_meter",
        title="LUGCUH50",
        entry_id="987654321",
        data=mock_entry_data,
    )
    assert mock_entry.data == mock_entry_data
    assert mock_entry.version == 1

    mock_entry.add_to_hass(hass)

    # Create entity entry to migrate to new unique ID
    registry = er.async_get(hass)
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        LANDISGYR_HEAT_METER_DOMAIN,
        "landisgyr_heat_meter_987654321_measuring_range_m3ph",
        suggested_object_id="heat_meter_measuring_range",
        config_entry=mock_entry,
    )

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert "landisgyr_heat_meter" in hass.config.components

    # Check if entity unique id is migrated successfully
    assert mock_entry.version == 2
    entity = registry.async_get("sensor.heat_meter_measuring_range")
    assert entity.unique_id == "12345_measuring_range_m3ph"
