"""Shared test fixtures and constants for Greencell integration tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.greencell.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.components.mqtt import MqttData
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Test constants
TEST_SERIAL_NUMBER = "EVGC021A2275XXXXXXXXXX"
TEST_SERIAL_NUMBER_2 = "EVGC021A2275YYYYYYYYYY"

# MQTT topics
TEST_CURRENT_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/current"
TEST_VOLTAGE_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/voltage"
TEST_POWER_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/power"
TEST_STATUS_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/status"
TEST_DEVICE_STATE_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/device_state"
TEST_DISCOVERY_TOPIC = f"/greencell/evse/{TEST_SERIAL_NUMBER}/discovery"

# MQTT message payloads - Current (in mA)
TEST_CURRENT_PAYLOAD_IDLE = b'{"l1": 0, "l2": 0, "l3": 0}'
TEST_CURRENT_PAYLOAD_3PHASE = b'{"l1": 2000, "l2": 2500, "l3": 3000}'
TEST_CURRENT_PAYLOAD_SINGLE = b'{"l1": 16500, "l2": 0, "l3": 0}'

# MQTT message payloads - Voltage (in V)
TEST_VOLTAGE_PAYLOAD_RESET = b'{"l1": 0, "l2": 0, "l3": 0}'
TEST_VOLTAGE_PAYLOAD_NORMAL = b'{"l1": 230.0, "l2": 229.7, "l3": 232.5}'
TEST_VOLTAGE_PAYLOAD_LOW = b'{"l1": 210.0, "l2": 209.7, "l3": 212.5}'
TEST_VOLTAGE_PAYLOAD_HIGH = b'{"l1": 245.0, "l2": 244.7, "l3": 247.5}'

# MQTT message payloads - Power (in W)
TEST_POWER_PAYLOAD_IDLE = b'{"momentary": 0.0}'
TEST_POWER_PAYLOAD_CHARGING = b'{"momentary": 1500.5}'
TEST_POWER_PAYLOAD_HIGH = b'{"momentary": 11000.0}'

# MQTT message payloads - Status
TEST_STATUS_PAYLOAD_IDLE = b'{"state": "IDLE"}'
TEST_STATUS_PAYLOAD_CONNECTED = b'{"state": "CONNECTED"}'
TEST_STATUS_PAYLOAD_CHARGING = b'{"state": "CHARGING"}'
TEST_STATUS_PAYLOAD_FINISHED = b'{"state": "FINISHED"}'
TEST_STATUS_PAYLOAD_ERROR = b'{"state": "ERROR_EVSE"}'
TEST_STATUS_PAYLOAD_UNAVAILABLE = b"UNAVAILABLE"
TEST_STATUS_PAYLOAD_OFFLINE = b"OFFLINE"

# MQTT message payloads - Device state
TEST_DEVICE_STATE_ONLINE = b'{"connected": true}'
TEST_DEVICE_STATE_OFFLINE = b'{"connected": false}'

# MQTT message payloads - Discovery
TEST_DISCOVERY_PAYLOAD = b'{"id": "EVGC021A2275XXXXXXXXXX"}'


@pytest.fixture
def mock_mqtt_data():
    """Mock MQTT data for async_fire_mqtt_message."""
    mqtt_data = MagicMock(spec=MqttData)
    mqtt_data.async_fire_internal_message = AsyncMock()

    # Mock the client and its connected status
    mqtt_data.client = MagicMock()
    mqtt_data.client.connected = True

    return mqtt_data


@pytest.fixture
async def setup_mqtt(hass: HomeAssistant, mock_mqtt_data):
    """Set up MQTT integration for testing."""
    # Mock the MQTT data in hass so async_fire_mqtt_message can find it
    hass.data["mqtt"] = mock_mqtt_data

    yield

    # Cleanup
    if "mqtt" in hass.data:
        del hass.data["mqtt"]


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry",
        data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER},
        title=f"Greencell {TEST_SERIAL_NUMBER}",
    )


@pytest.fixture
def mock_config_entry_2():
    """Return a second mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_2",
        data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER_2},
        title=f"Greencell {TEST_SERIAL_NUMBER_2}",
    )
