"""Shared test fixtures and constants for Greencell integration tests."""

import time

import pytest

from homeassistant.components.greencell.const import CONF_SERIAL_NUMBER, DOMAIN
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
            timestamp=time.time(),
        )

    return _make
