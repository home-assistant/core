"""Tests for sensors."""

from unittest.mock import AsyncMock, MagicMock

from ohme import ChargerStatus, OhmeApiClient
import pytest

from homeassistant.components.ohme.coordinator import OhmeCoordinator
from homeassistant.components.ohme.sensor import (
    SENSOR_DESCRIPTIONS,
    OhmeSensor,
    async_setup_entry,
)
from homeassistant.components.sensor import SensorDeviceClass


@pytest.fixture
def mock_coordinator():
    """Fixture to mock the OhmeCoordinator."""
    coordinator = MagicMock(spec=OhmeCoordinator)
    coordinator.data = MagicMock()
    return coordinator


@pytest.fixture
def mock_client():
    """Fixture to mock the OhmeApiClient."""
    client = MagicMock(spec=OhmeApiClient)
    client.status = ChargerStatus.CHARGING
    client.serial = "chargerid"
    client.ct_connected = True
    client.device_info = {
        "identifiers": ("ohme", "ohme_charger_chargerid"),
        "name": "Ohme Home Pro",
        "manufacturer": "Ohme",
        "model": "Home Pro",
        "sw_version": "1.0",
        "serial_number": "chargerid",
    }
    return client


@pytest.fixture
def mock_config_entry(mock_coordinator):
    """Fixture to mock a ConfigEntry."""
    config_entry = MagicMock()
    config_entry.runtime_data = mock_coordinator
    return config_entry


@pytest.mark.asyncio
async def test_async_setup_entry(
    mock_config_entry, mock_coordinator, mock_client
) -> None:
    """Test async_setup_entry sets up entities properly."""
    mock_coordinator.client = mock_client
    async_add_entities = AsyncMock()

    await async_setup_entry(None, mock_config_entry, async_add_entities)

    async_add_entities.assert_called_once()
    entities = async_add_entities.call_args[0][0]

    assert len(entities) == len(SENSOR_DESCRIPTIONS)
    for entity, description in zip(entities, SENSOR_DESCRIPTIONS, strict=False):
        assert isinstance(entity, OhmeSensor)
        assert entity.entity_description.key == description.key


def test_status_sensor(mock_coordinator, mock_client) -> None:
    """Test OhmeSensor properties return correct values."""
    description = SENSOR_DESCRIPTIONS[0]
    mock_coordinator.data = mock_client
    sensor = OhmeSensor(mock_coordinator, mock_client, description)

    native_value = sensor.native_value

    assert sensor.entity_description == description
    assert sensor.device_class == SensorDeviceClass.ENUM
    assert native_value == mock_client.status.value
