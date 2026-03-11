"""Shared test fixtures and constants for Greencell integration tests."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.greencell.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.components.mqtt import MqttData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

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
TEST_CURRENT_PAYLOAD_3PHASE = b'{"l1": 2000, "l2": 2500, "l3": 3000}'
TEST_CURRENT_PAYLOAD_SINGLE = b'{"l1": 16500, "l2": 0, "l3": 0}'

# MQTT message payloads - Voltage (in V)
TEST_VOLTAGE_PAYLOAD_NORMAL = b'{"l1": 230.0, "l2": 229.7, "l3": 232.5}'
TEST_VOLTAGE_PAYLOAD_SINGLE = b'{"l1": 230.0, "l2": 0.0, "l3": 0.0}'

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
TEST_STATUS_PAYLOAD_WAITING_FOR_CAR = b'{"state": "WAITING_FOR_CAR"}'
TEST_STATUS_PAYLOAD_ERROR_CAR = b'{"state": "ERROR_CAR"}'
TEST_STATUS_PAYLOAD_UNAVAILABLE = b"UNAVAILABLE"
TEST_STATUS_PAYLOAD_OFFLINE = b"OFFLINE"


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
    # Tworzymy mockowy wpis dla MQTT, aby przejść przez mqtt.async_wait_for_mqtt_client
    mqtt_entry = MockConfigEntry(
        domain="mqtt",
        data={"broker": "127.0.0.1"},
        state=ConfigEntryState.LOADED,
    )
    mqtt_entry.add_to_hass(hass)

    # Podpinamy dane MQTT do hass.data
    hass.data["mqtt"] = mock_mqtt_data

    yield

    # Sprzątanie po teście
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


@pytest.fixture
def mqtt_service_info():
    """Create a factory for MqttServiceInfo objects."""

    def _make(payload: str) -> MqttServiceInfo:
        return MqttServiceInfo(
            topic="greencell/broadcast/device",
            payload=payload,
            qos=0,
            retain=False,
            subscribed_topic="greencell/broadcast/device",
            timestamp=datetime.now(),
        )

    return _make
