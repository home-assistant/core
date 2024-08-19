"""Tests for the BSBLan sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.bsblan.coordinator import BSBLanUpdateCoordinator
from homeassistant.components.bsblan.models import BSBLanData
from homeassistant.components.bsblan.sensor import (
    SENSOR_TYPES,
    BSBLanSensor,
    BSBLanSensorEntityDescription,
    async_setup_entry,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=BSBLanUpdateCoordinator)
    coordinator.bsblan_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.100"}
    )
    coordinator.data = MagicMock()
    coordinator.data.sensor = MagicMock()
    coordinator.data.sensor.current_temperature = MagicMock(value="21.5")
    coordinator.data.sensor.outside_temperature = MagicMock(value="15.0")
    return coordinator


@pytest.fixture
def mock_bsblan_data(mock_coordinator) -> MagicMock:
    """Create a mocked BSBLanData instance."""
    mock_data = MagicMock(spec=BSBLanData)
    mock_data.coordinator = mock_coordinator
    mock_data.device = MagicMock()
    mock_data.device.MAC = "00:11:22:33:44:55"
    mock_data.device.name = "Test Device"
    mock_data.device.version = "1.0"
    mock_data.info = MagicMock()
    mock_data.info.device_identification = MagicMock()
    mock_data.info.device_identification.value = "Test Model"
    return mock_data


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        entry_id="testentry",
    )


def test_sensor_creation(
    hass: HomeAssistant, mock_coordinator, mock_bsblan_data
) -> None:
    """Test creation of sensors."""
    sensors = []
    for description in SENSOR_TYPES:
        sensor = BSBLanSensor(mock_coordinator, mock_bsblan_data, description)
        sensors.append(sensor)

    assert len(sensors) == len(SENSOR_TYPES)

    for sensor, description in zip(sensors, SENSOR_TYPES, strict=False):
        assert sensor.unique_id == f"{mock_bsblan_data.device.MAC}-{description.key}"
        assert sensor.name == description.translation_key.replace("_", " ").title()
        assert sensor.device_class == description.device_class
        assert (
            sensor.native_unit_of_measurement == description.native_unit_of_measurement
        )
        assert sensor.state_class == description.state_class
        assert sensor.translation_key == description.translation_key
        assert sensor.device_info == {
            "identifiers": {(DOMAIN, mock_bsblan_data.device.MAC)},
            "name": mock_bsblan_data.device.name,
            "manufacturer": "BSBLAN Inc.",
            "model": mock_bsblan_data.info.device_identification.value,
            "sw_version": mock_bsblan_data.device.version,
            "configuration_url": "http://192.168.1.100",
        }


@pytest.mark.parametrize("description", SENSOR_TYPES)
def test_sensor_values(
    hass: HomeAssistant, mock_coordinator, mock_bsblan_data, description
) -> None:
    """Test sensor values."""
    sensor = BSBLanSensor(mock_coordinator, mock_bsblan_data, description)

    if description.key == "current_temperature":
        assert sensor.native_value == 21.5
    elif description.key == "outside_temperature":
        assert sensor.native_value == 15.0


def test_generate_name() -> None:
    """Test the _generate_name static method."""
    assert BSBLanSensor._generate_name("test_key") == "Test Key"
    assert BSBLanSensor._generate_name(None) == "Unknown"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("23.5", 23.5),
        ("invalid", None),
        (None, None),
    ],
)
def test_native_value(
    hass: HomeAssistant, mock_coordinator, mock_bsblan_data, value, expected
) -> None:
    """Test the native_value property."""
    description = BSBLanSensorEntityDescription(
        key="test_sensor",
        translation_key="test_sensor",
        value_fn=lambda data: value,
    )
    sensor = BSBLanSensor(mock_coordinator, mock_bsblan_data, description)
    assert sensor.native_value == expected


async def test_async_setup_entry(
    hass: HomeAssistant, mock_bsblan_data, mock_config_entry
) -> None:
    """Test async_setup_entry function."""
    mock_config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = mock_bsblan_data

    with patch(
        "homeassistant.helpers.entity_platform.AddEntitiesCallback"
    ) as mock_add_entities:
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert mock_add_entities.call_count == 1
    entities = mock_add_entities.call_args[0][0]
    assert len(list(entities)) == len(SENSOR_TYPES)
    for entity in entities:
        assert isinstance(entity, BSBLanSensor)


@pytest.mark.parametrize("description", SENSOR_TYPES)
def test_sensor_update(
    hass: HomeAssistant, mock_coordinator, mock_bsblan_data, description
) -> None:
    """Test sensor update."""
    sensor = BSBLanSensor(mock_coordinator, mock_bsblan_data, description)

    # Simulate a coordinator update
    if description.key == "current_temperature":
        mock_coordinator.data.sensor.current_temperature.value = "22.5"
    elif description.key == "outside_temperature":
        mock_coordinator.data.sensor.outside_temperature.value = "16.0"

    mock_coordinator.async_set_updated_data(mock_coordinator.data)

    if description.key == "current_temperature":
        assert sensor.native_value == 22.5
    elif description.key == "outside_temperature":
        assert sensor.native_value == 16.0


def test_sensor_availability(
    hass: HomeAssistant, mock_coordinator, mock_bsblan_data
) -> None:
    """Test sensor availability."""
    sensor = BSBLanSensor(mock_coordinator, mock_bsblan_data, SENSOR_TYPES[0])

    # Test when coordinator is available
    mock_coordinator.last_update_success = True
    assert sensor.available is True

    # Test when coordinator is not available
    mock_coordinator.last_update_success = False
    assert sensor.available is False


@pytest.mark.asyncio
async def test_async_added_to_hass(
    hass: HomeAssistant, mock_coordinator, mock_bsblan_data
) -> None:
    """Test async_added_to_hass method."""
    sensor = BSBLanSensor(mock_coordinator, mock_bsblan_data, SENSOR_TYPES[0])

    with patch.object(sensor, "async_on_remove") as mock_async_on_remove:
        await sensor.async_added_to_hass()

    assert mock_async_on_remove.called
    assert mock_coordinator.async_add_listener.called
