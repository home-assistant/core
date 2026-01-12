"""Global fixtures for uHoo integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.uhoo.sensor import (
    SENSOR_TYPES,
    SensorDeviceClass,
    SensorStateClass,
    UnitOfTemperature,
)
from homeassistant.const import CONF_API_KEY, PERCENTAGE
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def mock_device():
    """Mock a uHoo device."""
    device = MagicMock()
    device.humidity = 45.5
    device.temperature = 22.0
    device.co = 1.5
    device.co2 = 450.0
    device.pm25 = 12.3
    device.air_pressure = 1013.25
    device.tvoc = 150.0
    device.no2 = 20.0
    device.ozone = 30.0
    device.virus_index = 2.0
    device.mold_index = 1.5
    device.device_name = "Test Device"
    device.serial_number = "23f9239m92m3ffkkdkdd"
    device.user_settings = {"temp": "c"}
    return device


@pytest.fixture(name="mock_uhoo_client")
def mock_uhoo_client(mock_device) -> Generator[AsyncMock]:
    """Mock uHoo client."""
    with (
        patch(
            "homeassistant.components.uhoo.config_flow.Client",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.uhoo.Client",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login = AsyncMock()
        client.setup_devices = AsyncMock()
        client.get_devices = MagicMock()
        client.get_latest_data = AsyncMock(
            return_value=[
                {
                    "serialNumber": "23f9239m92m3ffkkdkdd",
                    "deviceName": "Test Device",
                    "humidity": 45.5,
                    "temperature": 22.0,
                    "co": 0.0,
                    "co2": 400.0,
                    "pm25": 10.0,
                    "airPressure": 1010.0,
                    "tvoc": 100.0,
                    "no2": 15.0,
                    "ozone": 25.0,
                    "virusIndex": 1.0,
                    "moldIndex": 1.0,
                    "userSettings": {"temp": "c"},
                }
            ]
        )
        client.devices = {"23f9239m92m3ffkkdkdd": mock_device}
        yield client


@pytest.fixture(name="mock_uhoo_config_entry")
def mock_uhoo_config_entry_fixture() -> MockConfigEntry:
    """Return a mocked config entry for uHoo integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="valid-api-key-12345",
        data={CONF_API_KEY: "valid-api-key-12345"},
        title="uHoo (12345)",
        entry_id="01J0BC4QM2YBRP6H5G933CETT7",
    )


@pytest.fixture(name="mock_add_entities")
def mock_add_entities():
    """Mock the add_entities callback."""
    return MagicMock(spec=AddConfigEntryEntitiesCallback)


@pytest.fixture(name="test_sensor_entity_descriptions")
def test_sensor_entity_descriptions() -> None:
    """Test that all sensor descriptions are properly defined."""
    assert len(SENSOR_TYPES) == 11  # We have 11 sensor types

    # Check a few key sensors
    humidity_desc = next(d for d in SENSOR_TYPES if d.key == "humidity")
    assert humidity_desc.device_class == SensorDeviceClass.HUMIDITY
    assert humidity_desc.native_unit_of_measurement == PERCENTAGE
    assert humidity_desc.state_class == SensorStateClass.MEASUREMENT
    assert callable(humidity_desc.value_fn)

    temp_desc = next(d for d in SENSOR_TYPES if d.key == "temperature")
    assert temp_desc.device_class == SensorDeviceClass.TEMPERATURE
    assert temp_desc.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert temp_desc.state_class == SensorStateClass.MEASUREMENT
    assert callable(temp_desc.value_fn)

    # Check virus and mold sensors don't have device_class
    virus_desc = next(d for d in SENSOR_TYPES if d.key == "virus_index")
    mold_desc = next(d for d in SENSOR_TYPES if d.key == "mold_index")
    assert virus_desc.device_class is None
    assert mold_desc.device_class is None


@pytest.fixture(name="mock_uhoo_coordinator")
def mock_uhoo_coordinator_fixture(mock_uhoo_client):
    """Mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.client = mock_uhoo_client
    return coordinator


@pytest.fixture
def patch_async_get_clientsession():
    """Patch async_get_clientsession to return a mock."""
    with patch(
        "homeassistant.components.uhoo.async_get_clientsession",
        return_value=AsyncMock(),
    ) as mock_session:
        yield mock_session


@pytest.fixture
def patch_uhoo_data_update_coordinator(mock_uhoo_coordinator):
    """Patch UhooDataUpdateCoordinator to return mock coordinator."""
    with patch(
        "homeassistant.components.uhoo.UhooDataUpdateCoordinator",
        return_value=mock_uhoo_coordinator,
    ) as mock_coordinator_class:
        yield mock_coordinator_class


@pytest.fixture(name="mock_setup_entry")
def mock_setup_entry_fixture():
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.uhoo.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations() -> None:
    """This fixture enables loading custom integrations in all tests."""
    return


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield
