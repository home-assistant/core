"""Test fixtures for qbus."""

import time
from unittest.mock import AsyncMock, Mock

import pytest
from qbusmqttapi.const import KEY_OUTPUT_ID, KEY_OUTPUT_REF_ID
from qbusmqttapi.discovery import QbusMqttOutput

from homeassistant.components.qbus.config_flow import QbusFlowHandler
from homeassistant.components.qbus.switch import QbusSwitch
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
def qbus_switch_1(hass: HomeAssistant) -> QbusSwitch:
    """Create Qbus switch handler ."""
    mqtt_output = QbusMqttOutput(
        {KEY_OUTPUT_ID: "UL10", KEY_OUTPUT_REF_ID: "000001/10"},
        Mock(id="UL1", serial_number="000001", mac="00:11:22:33:44:55"),
    )

    qbus_switch = QbusSwitch(mqtt_output)
    qbus_switch.hass = hass
    qbus_switch.unique_id = "ctd_000001_10"
    qbus_switch.entity_id = "switch.qbus_000001_10"

    return qbus_switch


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
def mqtt_discovery_info_device():
    """Create MQTT discovery info for a device state topic."""
    return MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload="{ }",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )
