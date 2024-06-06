"""Test the Leslie's Pool Water Tests sensors."""

from datetime import timedelta
import logging
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.leslies_pool.const import DOMAIN
from homeassistant.components.leslies_pool.sensor import (
    LesliesPoolSensor,
    async_setup_entry,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    "free_chlorine": ("Free Chlorine", "ppm"),
    "total_chlorine": ("Total Chlorine", "ppm"),
    "ph": ("pH", "pH"),
    "alkalinity": ("Total Alkalinity", "ppm"),
    "calcium": ("Calcium Hardness", "ppm"),
    "cyanuric_acid": ("Cyanuric Acid", "ppm"),
    "iron": ("Iron", "ppm"),
    "copper": ("Copper", "ppm"),
    "phosphates": ("Phosphates", "ppb"),
    "salt": ("Salt", "ppm"),
}


@pytest.fixture
def mock_coordinator(hass):
    """Mock a coordinator."""
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="leslies_pool",
        update_method=AsyncMock(return_value={sensor: 1 for sensor in SENSOR_TYPES}),
        update_interval=timedelta(seconds=300),
    )
    coordinator.data = {sensor: 1 for sensor in SENSOR_TYPES}
    coordinator.async_refresh = AsyncMock()
    coordinator.async_add_listener = AsyncMock()
    return coordinator


async def test_async_setup_entry(hass, mock_coordinator):
    """Test setting up the config entry."""
    mock_entry = AsyncMock()
    mock_entry.entry_id = "test_entry"
    mock_entry.data = {
        "username": "test-username",
        "password": "test-password",
        "scan_interval": 300,
    }

    hass.data = {DOMAIN: {mock_entry.entry_id: mock_coordinator}}

    async_add_entities = AsyncMock()

    with patch(
        "homeassistant.components.leslies_pool.api.LesliesPoolApi",
        return_value=AsyncMock(),
    ):
        await async_setup_entry(hass, mock_entry, async_add_entities)

    assert async_add_entities.call_count == 1
    assert len(async_add_entities.call_args[0][0]) == len(SENSOR_TYPES)


async def test_sensor_properties(hass, mock_coordinator):
    """Test sensor properties."""
    mock_entry = AsyncMock()
    mock_entry.entry_id = "test_entry"

    sensor = LesliesPoolSensor(
        mock_coordinator, mock_entry, "free_chlorine", "Free Chlorine", "ppm"
    )

    assert sensor.unique_id == "test_entry_free_chlorine"
    assert sensor.name == "Free Chlorine"
    assert sensor.state == 1
    assert sensor.available
    assert sensor.device_info == {
        "identifiers": {(DOMAIN, "test_entry")},
        "name": "Leslie's Pool",
        "manufacturer": "Leslie's Pool",
        "model": "Water Test",
        "entry_type": "service",
    }
    assert sensor.unit_of_measurement == "ppm"


async def test_sensor_update(hass, mock_coordinator):
    """Test sensor update."""
    mock_entry = AsyncMock()
    mock_entry.entry_id = "test_entry"

    sensor = LesliesPoolSensor(
        mock_coordinator, mock_entry, "free_chlorine", "Free Chlorine", "ppm"
    )

    with patch.object(
        sensor.coordinator, "async_request_refresh", AsyncMock()
    ) as mock_refresh:
        await sensor.async_update()
        assert mock_refresh.call_count == 1


async def test_sensor_added_to_hass(hass, mock_coordinator):
    """Test sensor added to hass."""
    mock_entry = AsyncMock()
    mock_entry.entry_id = "test_entry"

    sensor = LesliesPoolSensor(
        mock_coordinator, mock_entry, "free_chlorine", "Free Chlorine", "ppm"
    )

    with patch.object(sensor, "async_write_ha_state", AsyncMock()):
        await sensor.async_added_to_hass()
        assert mock_coordinator.async_add_listener.call_count == 1
        assert (
            mock_coordinator.async_add_listener.call_args[0][0]
            == sensor.async_write_ha_state
        )
