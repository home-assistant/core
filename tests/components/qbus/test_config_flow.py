"""Test config flow."""

import json
import time
from unittest.mock import patch

from qbusmqttapi.discovery import QbusDiscovery

from homeassistant.components.qbus.const import CONF_ID, CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.components.qbus.coordinator import QbusConfigCoordinator
from homeassistant.config_entries import SOURCE_MQTT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .common import PAYLOAD_CONFIG, TOPIC_CONFIG


async def test_step_mqtt_empty_payload(hass: HomeAssistant) -> None:
    """Test mqtt discovery with empty payload."""
    discovery = MqttServiceInfo(
        subscribed_topic="",
        topic="",
        payload=b"",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_step_mqtt_invalid_topic(hass: HomeAssistant) -> None:
    """Test mqtt discovery with an invalid topic."""
    discovery = MqttServiceInfo(
        subscribed_topic="invalid/topic",
        topic="",
        payload=b"{}",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_handle_gateway_topic_when_online(hass: HomeAssistant) -> None:
    """Test handling of gateway topic with payload indicating online."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/state",
        topic="cloudapp/QBUSMQTTGW/state",
        payload='{ "online": true }',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with (
        patch("homeassistant.components.mqtt.client.async_publish") as mock_publish,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert mock_publish.called
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_gateway_topic_when_offline(hass: HomeAssistant) -> None:
    """Test handling of gateway topic with payload indicating offline."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/state",
        topic="cloudapp/QBUSMQTTGW/state",
        payload='{ "online": false }',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with (
        patch("homeassistant.components.mqtt.client.async_publish") as mock_publish,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert mock_publish.called is False
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_config_topic(hass: HomeAssistant) -> None:
    """Test handling of config topic."""
    discovery = MqttServiceInfo(
        subscribed_topic=TOPIC_CONFIG,
        topic=TOPIC_CONFIG,
        payload=PAYLOAD_CONFIG,
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with (
        patch.object(
            QbusConfigCoordinator, "store_config", return_value=None, autospec=True
        ) as mock_store,
        patch("homeassistant.components.mqtt.client.async_publish") as mock_publish,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert mock_store.called
    assert mock_publish.called
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_device_topic_missing_config(hass: HomeAssistant) -> None:
    """Test handling of device topic when config is missing."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload="{ }",
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with (
        patch.object(
            QbusConfigCoordinator,
            "async_get_or_request_config",
            return_value=None,
        ) as mock_get_config,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert mock_get_config.called
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_handle_device_topic_config_not_ready(hass: HomeAssistant) -> None:
    """Test handling of device topic when device is not found."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload='{"id":"UL1","properties":{"connected":true},"type":"event"}',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with patch.object(
        QbusConfigCoordinator,
        "async_get_or_request_config",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_handle_device_topic_device_not_found(hass: HomeAssistant) -> None:
    """Test handling of device topic when device is not found."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload='{"id":"UL1","properties":{"connected":true},"type":"event"}',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with patch.object(
        QbusConfigCoordinator,
        "async_get_or_request_config",
        return_value=QbusDiscovery(json.loads(PAYLOAD_CONFIG.replace("UL1", "UL2"))),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_step_discovery_confirm_create_entry(hass: HomeAssistant) -> None:
    """Test mqtt confirm creating the entry."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload='{"id":"UL1","properties":{"connected":true},"type":"event"}',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with (
        patch.object(
            QbusConfigCoordinator,
            "async_get_or_request_config",
            return_value=QbusDiscovery(json.loads(PAYLOAD_CONFIG)),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_ID: "UL1",
        CONF_SERIAL_NUMBER: "000001",
    }


async def test_step_user_not_supported(hass: HomeAssistant) -> None:
    """Test user step, which should abort."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"
