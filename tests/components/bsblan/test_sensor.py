"""Tests for the BSBLan device config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.sensor import BSBLANSensor
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "sensor": MagicMock(
            test_sensor=MagicMock(value="21.5", unit="°C"),
        )
    }
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_bsblan():
    """Create a mock BSBLAN client."""
    return MagicMock()


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"host": "test-host", "port": 80, "passkey": "test-passkey"},
    )


def test_sensor_device_class(
    hass: HomeAssistant, mock_coordinator, mock_bsblan, mock_config_entry
) -> None:
    """Test the device class of BSBLAN sensors."""
    sensor = BSBLANSensor(
        coordinator=mock_coordinator,
        client=mock_bsblan,
        device=MagicMock(MAC="00:11:22:33:44:55", name="Test Device"),
        info=MagicMock(device_identification=MagicMock(value="Test Model")),
        static=MagicMock(),
        entry=mock_config_entry,
        key="test_sensor",
        name="Test Sensor",
        unit=UnitOfTemperature.CELSIUS,
    )
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE

    sensor._attr_native_unit_of_measurement = UnitOfPressure.BAR
    assert sensor.device_class == SensorDeviceClass.PRESSURE

    sensor._attr_native_unit_of_measurement = PERCENTAGE
    assert sensor.device_class == SensorDeviceClass.POWER_FACTOR

    sensor._attr_native_unit_of_measurement = "unknown"
    assert sensor.device_class is None


def test_sensor_state_class(
    hass: HomeAssistant, mock_coordinator, mock_bsblan, mock_config_entry
) -> None:
    """Test the state class of BSBLAN sensors."""
    sensor = BSBLANSensor(
        coordinator=mock_coordinator,
        client=mock_bsblan,
        device=MagicMock(MAC="00:11:22:33:44:55", name="Test Device"),
        info=MagicMock(device_identification=MagicMock(value="Test Model")),
        static=MagicMock(),
        entry=mock_config_entry,
        key="test_sensor",
        name="Test Sensor",
        unit=UnitOfTemperature.CELSIUS,
    )
    assert sensor.state_class == SensorStateClass.MEASUREMENT


async def test_sensor_update(
    hass: HomeAssistant, mock_coordinator, mock_bsblan, mock_config_entry
) -> None:
    """Test updating BSBLAN sensor."""
    sensor = BSBLANSensor(
        coordinator=mock_coordinator,
        client=mock_bsblan,
        device=MagicMock(MAC="00:11:22:33:44:55", name="Test Device"),
        info=MagicMock(device_identification=MagicMock(value="Test Model")),
        static=MagicMock(),
        entry=mock_config_entry,
        key="test_sensor",
        name="Test Sensor",
        unit=UnitOfTemperature.CELSIUS,
    )

    assert sensor.native_value == "21.5"

    mock_coordinator.data["sensor"].test_sensor.value = "22.0"
    await hass.async_block_till_done()

    assert sensor.native_value == "22.0"
