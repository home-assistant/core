"""Tests for climate capabilities."""

from unittest.mock import AsyncMock, patch

from custom_components.mill_wifi.api import MillApiClient
from custom_components.mill_wifi.const import DOMAIN
from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.device_capability import EDeviceCapability, EDeviceType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

MOCK_DEVICE_ID = "test_heater_123"
MOCK_DEVICE_DATA_HEAT_OFF = {
    MOCK_DEVICE_ID: {
        "deviceId": MOCK_DEVICE_ID,
        "customName": "Test Heater",
        "deviceType": {
            "childType": {"name": "GL-Panel Heater G3"},
            "parentType": {"name": "Heaters"},
        },
        "isEnabled": False,
        "deviceSettings": {
            "reported": {
                "temperature_normal": 20.0,
                "operation_mode": "control_individually",
            }
        },
        "lastMetrics": {"temperatureAmbient": 18.0, "heaterFlag": 0},
    }
}
MOCK_DEVICE_DATA_HEAT_ON_HEATING = {
    MOCK_DEVICE_ID: {
        "deviceId": MOCK_DEVICE_ID,
        "customName": "Test Heater",
        "deviceType": {
            "childType": {"name": "GL-Panel Heater G3"},
            "parentType": {"name": "Heaters"},
        },
        "isEnabled": True,
        "deviceSettings": {
            "reported": {
                "temperature_normal": 22.0,
                "operation_mode": "control_individually",
            }
        },
        "lastMetrics": {"temperatureAmbient": 18.0, "heaterFlag": 1},
    }
}


@pytest.fixture
def mock_mill_api_client():
    """Mock Mill API client."""
    client = AsyncMock(spec=MillApiClient)
    client.connect = AsyncMock(return_value=True)
    client.get_all_devices = AsyncMock(
        return_value=[
            {
                "deviceId": "test_heater_01",
                "deviceName": "Test Heater",
                "type": EDeviceType.PANEL_HEATER_GEN3.value,
                "capabilities": [
                    EDeviceCapability.ONOFF.value,
                    EDeviceCapability.TARGET_TEMPERATURE.value,
                    EDeviceCapability.MEASURE_TEMPERATURE.value,
                ],
                "reported": {
                    "powerState": "on",
                    "temperature": 20.0,
                    "targetTemperature": 22.0,
                    "mode": "heat",
                },
                "deviceSettings": {"temperatureNormal": 22.0},  # Example
            }
        ]
    )
    client.set_device_temperature = AsyncMock(return_value=True)
    client.set_device_hvac_mode = AsyncMock(return_value=True)
    return client


async def setup_integration_with_entry(
    hass: HomeAssistant, mock_api_client, entry: MockConfigEntry
):
    """Help to set up the integration with a given config entry and mocked API."""

    entry.add_to_hass(hass)
    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_api_client,
    ):
        assert await hass.config_entries.async_setup(
            entry.entry_id
        )
        await hass.async_block_till_done()
    return entry


@pytest.mark.asyncio
async def test_climate_entity_creation_and_initial_state(
    hass: HomeAssistant, mock_mill_api_client
):
    """Test climate entity is created and reports initial state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.com", "password": "password"},
        entry_id="test_climate_init",
    )
    await setup_integration_with_entry(hass, mock_mill_api_client, entry)

    entity_id = "climate.test_heater"
    state = hass.states.get(entity_id)
    assert state is not None, (
        f"State for {entity_id} was None. States: {hass.states.async_all()}"
    )
    assert state.state == HVACMode.OFF
    assert state.attributes.get("current_temperature") == 18.0
    assert state.attributes.get("temperature") == 20.0
    assert state.attributes.get("hvac_action") == HVACAction.OFF


@pytest.mark.asyncio
async def test_climate_set_temperature(hass: HomeAssistant, mock_mill_api_client):
    """Test setting temperature for the climate entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.com", "password": "password"},
        entry_id="test_climate_set_temp",
    )
    # Initial setup with device off
    mock_mill_api_client.get_all_devices.return_value = [
        MOCK_DEVICE_DATA_HEAT_OFF[MOCK_DEVICE_ID]
    ]
    await setup_integration_with_entry(hass, mock_mill_api_client, entry)

    entity_id = "climate.test_heater"

    # Simulate that the coordinator gets updated data showing the device is on
    # (or that setting temperature will turn it on and use this data)
    coordinator: MillDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.data = MOCK_DEVICE_DATA_HEAT_ON_HEATING
    coordinator.async_set_updated_data(MOCK_DEVICE_DATA_HEAT_ON_HEATING)
    await hass.async_block_till_done()

    current_state = hass.states.get(entity_id)
    if current_state and current_state.state == HVACMode.OFF:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )
        # Reset mock for set_device_power if it was called during set_hvac_mode
        mock_mill_api_client.set_device_power.reset_mock()
        # Refresh coordinator data after HVAC mode change if necessary for subsequent calls
        mock_mill_api_client.get_all_devices.return_value = [
            MOCK_DEVICE_DATA_HEAT_ON_HEATING[MOCK_DEVICE_ID]
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {"entity_id": entity_id, ATTR_TEMPERATURE: 23.0},
        blocking=True,
    )

    mock_mill_api_client.set_number_capability.assert_called_once_with(
        MOCK_DEVICE_ID,
        EDeviceCapability.TARGET_TEMPERATURE.value,
        23.0,
        MOCK_DEVICE_DATA_HEAT_ON_HEATING[MOCK_DEVICE_ID],
    )


@pytest.mark.asyncio
async def test_climate_set_hvac_mode_heat(hass: HomeAssistant, mock_mill_api_client):
    """Test setting HVAC mode to HEAT."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.com", "password": "password"},
        entry_id="test_climate_set_hvac",
    )
    # Start with device off
    mock_mill_api_client.get_all_devices.return_value = [
        MOCK_DEVICE_DATA_HEAT_OFF[MOCK_DEVICE_ID]
    ]
    await setup_integration_with_entry(hass, mock_mill_api_client, entry)

    entity_id = "climate.test_heater"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )

    mock_mill_api_client.set_device_power.assert_called_with(
        MOCK_DEVICE_ID, True, MOCK_DEVICE_DATA_HEAT_OFF[MOCK_DEVICE_ID]
    )
