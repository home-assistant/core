"""Tests for the Mill WiFi sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.mill_wifi.api import MillApiClient
from custom_components.mill_wifi.const import DOMAIN
from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.device_capability import EDeviceCapability, EDeviceType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant

# --- MOCK DATA ---
MOCK_HEATER_ID_SENSOR = "heater_sensor_1"
MOCK_HEATER_NAME_SENSOR = "Hallway Heater"
MOCK_DEVICE_DATA_HEATER = {
    MOCK_HEATER_ID_SENSOR: {
        "deviceId": MOCK_HEATER_ID_SENSOR,
        "customName": MOCK_HEATER_NAME_SENSOR,
        "deviceType": {"childType": {"name": EDeviceType.PANEL_HEATER_GEN3.value}},
        "isEnabled": True,
        "isConnected": True,
        "lastMetrics": {"temperature_ambient": 21.3, "humidity_ambient": 45},
        "capabilities": [
            EDeviceCapability.MEASURE_TEMPERATURE.value,
            EDeviceCapability.MEASURE_HUMIDITY.value,
        ],
    }
}

MOCK_PURIFIER_ID_SENSOR = "purifier_sensor_1"
MOCK_PURIFIER_NAME_SENSOR = "Kitchen Purifier"
MOCK_DEVICE_DATA_PURIFIER = {
    MOCK_PURIFIER_ID_SENSOR: {
        "deviceId": MOCK_PURIFIER_ID_SENSOR,
        "customName": MOCK_PURIFIER_NAME_SENSOR,
        "deviceType": {"childType": {"name": EDeviceType.AIR_PURIFIER_L.value}},
        "isEnabled": True,
        "isConnected": True,
        "lastMetrics": {
            "temperature_ambient": 22.1,
            "humidity_ambient": 50,
            "pm25_value": 10,
            "pm10_value": 15,
            "voc_value": 120,
            "co2_value": 450,
            "tvoc_value": 200,
            "filter_remain_percentage": 85,
        },
        "capabilities": [
            EDeviceCapability.MEASURE_TEMPERATURE.value,
            EDeviceCapability.MEASURE_HUMIDITY.value,
            EDeviceCapability.MEASURE_PM25.value,
            EDeviceCapability.MEASURE_PM10.value,
            EDeviceCapability.MEASURE_TVOC.value,
            EDeviceCapability.MEASURE_CO2.value,
            EDeviceCapability.MEASURE_TVOC.value,
            EDeviceCapability.MEASURE_FILTER_STATE.value,
        ],
    }
}


# --- PYTEST FIXTURES ---
@pytest.fixture
def mock_mill_api_client_fixture():
    """Mock pytest fixtures."""

    client = MagicMock(spec=MillApiClient)
    client.login = AsyncMock(return_value=None)
    client.async_setup = AsyncMock(return_value=None)
    client.get_all_devices = AsyncMock(
        return_value=[MOCK_DEVICE_DATA_HEATER[MOCK_HEATER_ID_SENSOR]]
    )
    return client


@pytest.fixture
async def setup_integration_fixture(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Set integration fixtures."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.com", "password": "password"},
        entry_id="test_sensor_entry_fixture",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        mock_mill_api_client_fixture.get_all_devices.return_value = [
            MOCK_DEVICE_DATA_HEATER[MOCK_HEATER_ID_SENSOR]
        ]

        assert await hass.config_entries.async_setup(entry.entry_id) is True, (
            "Failed to set up config entry"
        )
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if not coordinator.data:
        coordinator.data = {
            MOCK_HEATER_ID_SENSOR: MOCK_DEVICE_DATA_HEATER[MOCK_HEATER_ID_SENSOR]
        }
    await hass.async_block_till_done()
    return entry


# --- TEST CASES ---
async def test_no_sensors_if_no_devices(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Tests no devices."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "pwd"},
        entry_id="no_sensor_devices_entry",
    )
    entry.add_to_hass(hass)
    mock_mill_api_client_fixture.get_all_devices.return_value = []

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    assert len(hass.states.async_all(SENSOR_DOMAIN)) == 0


async def test_temperature_sensor_creation(
    hass: HomeAssistant, setup_integration_fixture: MockConfigEntry
):
    """Tests temperature sensor creation."""

    entity_id = f"{SENSOR_DOMAIN}.{MOCK_HEATER_NAME_SENSOR.lower().replace(' ', '_')}_temperature"
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == "21.3"
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS
    assert state.attributes.get("device_class") == "temperature"


async def test_humidity_sensor_creation(
    hass: HomeAssistant, setup_integration_fixture: MockConfigEntry
):
    """Tests humidity sensor creation."""


    entity_id = (
        f"{SENSOR_DOMAIN}.{MOCK_HEATER_NAME_SENSOR.lower().replace(' ', '_')}_humidity"
    )
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == "45"
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE
    assert state.attributes.get("device_class") == "humidity"


async def test_air_purifier_sensors_creation(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Tests air purifiers sensors creation."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "pwd"},
        entry_id="purifier_sensor_entry",
    )
    entry.add_to_hass(hass)

    mock_mill_api_client_fixture.get_all_devices.return_value = [
        MOCK_DEVICE_DATA_PURIFIER[MOCK_PURIFIER_ID_SENSOR]
    ]

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.data = {
        MOCK_PURIFIER_ID_SENSOR: MOCK_DEVICE_DATA_PURIFIER[MOCK_PURIFIER_ID_SENSOR]
    }
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    expected_sensors = {
        EDeviceCapability.MEASURE_TEMPERATURE: "22.1",
        EDeviceCapability.MEASURE_HUMIDITY: "50",
        EDeviceCapability.MEASURE_PM25: "10",
        EDeviceCapability.MEASURE_PM10: "15",
        EDeviceCapability.VOC: "120",
        EDeviceCapability.CO2: "450",
        EDeviceCapability.TVOC: "200",
        EDeviceCapability.FILTER_LIFE: "85",
    }

    for cap, expected_value in expected_sensors.items():
        entity_id = f"{SENSOR_DOMAIN}.{MOCK_PURIFIER_NAME_SENSOR.lower().replace(' ', '_')}_{cap.value.lower().replace(' ', '_')}"
        state = hass.states.get(entity_id)
        assert state is not None, f"Entity {entity_id} not found"
        assert state.state == expected_value
