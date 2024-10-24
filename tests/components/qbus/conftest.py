"""Test fixtures for qbus."""

import time
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.qbus.config_flow import QbusFlowHandler
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo


@pytest.fixture
def qbus_config_flow(hass: HomeAssistant) -> QbusFlowHandler:
    """Create Qbus flow handler."""
    config_flow = QbusFlowHandler()
    config_flow.hass = hass
    config_flow.async_set_unique_id = AsyncMock()
    config_flow.context = Mock()
    return config_flow


@pytest.fixture
def qbus_config_flow_with_device(hass: HomeAssistant) -> QbusFlowHandler:
    """Create Qbus flow handler with device."""
    config_flow = QbusFlowHandler()
    config_flow.hass = hass
    config_flow.async_set_unique_id = AsyncMock()
    config_flow.context = Mock()
    config_flow._device = Mock(id="UL1", serial_number="000001")
    return config_flow


@pytest.fixture
def mqtt_discovery_info():
    """Create MQTT discovery info."""
    return MqttServiceInfo(
        subscribed_topic="",
        topic="",
        payload=b"",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )


@pytest.fixture
def mqtt_discovery_info_gateway():
    """Create MQTT discovery info for a gateway state topic."""
    return MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/state",
        topic="cloudapp/QBUSMQTTGW/state",
        payload='{ "online": true }',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )


@pytest.fixture
def mqtt_discovery_info_config():
    """Create MQTT discovery info for a config topic."""
    return MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/config",
        topic="cloudapp/QBUSMQTTGW/config",
        payload="{ }",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )


@pytest.fixture
def mqtt_discovery_info_controller():
    """Create MQTT discovery info for a controller state topic."""
    return MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload="{ }",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )
