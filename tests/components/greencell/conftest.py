"""Shared test fixtures and constants for Greencell integration tests."""

import time
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt as real_mqtt
from homeassistant.components.greencell.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    GREENCELL_BROADCAST_TOPIC,
    GREENCELL_DISC_TOPIC,
)
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

# Test constants
TEST_SERIAL_NUMBER = "EVGC021A22750001ZM0001"
TEST_SERIAL_NUMBER_2 = "EVGC021A22750002ZM0002"

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
TEST_DEVICE_STATE_PAYLOAD_EXECUTE = b'{"level": "EXECUTE"}'


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry",
        data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER},
        title=f"Greencell {TEST_SERIAL_NUMBER}",
        unique_id=TEST_SERIAL_NUMBER,
    )


@pytest.fixture
def mock_config_entry_2():
    """Return a second mock config entry for testing."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_2",
        data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER_2},
        title=f"Greencell {TEST_SERIAL_NUMBER_2}",
        unique_id=TEST_SERIAL_NUMBER_2,
    )


@pytest.fixture
def mqtt_service_info():
    """Create a factory for MqttServiceInfo objects."""

    def _make(payload: str) -> MqttServiceInfo:
        return MqttServiceInfo(
            topic=GREENCELL_DISC_TOPIC,
            payload=payload,
            qos=0,
            retain=False,
            subscribed_topic=GREENCELL_BROADCAST_TOPIC,
            timestamp=time.time(),
        )

    return _make


@pytest.fixture
def mock_setup_entry():
    """Override async_setup_entry to prevent the integration from starting."""
    with patch(
        "homeassistant.components.greencell.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mqtt_mock: MqttMockHAClient,
) -> MockConfigEntry:
    """Set up the greencell integration with device-ready fired synchronously."""

    mock_config_entry.add_to_hass(hass)
    real_async_subscribe = real_mqtt.async_subscribe

    async def _mock_init_subscribe(hass_arg, topic, msg_callback, *args, **kwargs):
        """Fire discovery payload immediately, pass everything else through."""
        if topic == GREENCELL_DISC_TOPIC:
            msg_callback(
                ReceiveMessage(
                    topic=GREENCELL_DISC_TOPIC,
                    payload=f'{{"id": "{TEST_SERIAL_NUMBER}"}}',
                    qos=0,
                    retain=False,
                    subscribed_topic=GREENCELL_DISC_TOPIC,
                    timestamp=time.time(),
                )
            )
            return lambda: None
        return await real_async_subscribe(
            hass_arg, topic, msg_callback, *args, **kwargs
        )

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=_mock_init_subscribe,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
