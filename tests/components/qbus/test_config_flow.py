"""Test config flow."""

import json
import time
from unittest.mock import patch

import pytest
from qbusmqttapi.discovery import QbusDiscovery

from homeassistant.components.qbus.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.components.qbus.coordinator import QbusConfigCoordinator
from homeassistant.config_entries import SOURCE_MQTT, SOURCE_USER
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import FIXTURE_PAYLOAD_CONFIG, TOPIC_CONFIG

from tests.common import load_json_object_fixture

_PAYLOAD_DEVICE_STATE = '{"id":"UL1","properties":{"connected":true},"type":"event"}'


async def test_step_discovery_confirm_create_entry(hass: HomeAssistant) -> None:
    """Test mqtt confirm step and entry creation."""

    payload_config = load_json_object_fixture(FIXTURE_PAYLOAD_CONFIG, DOMAIN)

    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL1/state",
        payload=_PAYLOAD_DEVICE_STATE,
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with (
        patch.object(
            QbusConfigCoordinator,
            "async_get_or_request_config",
            return_value=QbusDiscovery(payload_config),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_ID: "UL1",
        CONF_SERIAL_NUMBER: "000001",
    }
    assert result.get("result").unique_id == "000001"


@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        ("cloudapp/QBUSMQTTGW/state", b""),
        ("invalid/topic", b"{}"),
    ],
)
async def test_step_mqtt_invalid(
    hass: HomeAssistant, topic: str, payload: bytes
) -> None:
    """Test mqtt discovery with empty payload."""
    discovery = MqttServiceInfo(
        subscribed_topic=topic,
        topic=topic,
        payload=payload,
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


@pytest.mark.parametrize(
    ("payload", "mqtt_publish"),
    [
        ('{ "online": true }', True),
        ('{ "online": false }', False),
    ],
)
async def test_handle_gateway_topic_when_online(
    hass: HomeAssistant, payload: str, mqtt_publish: bool
) -> None:
    """Test handling of gateway topic with payload indicating online."""
    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/state",
        topic="cloudapp/QBUSMQTTGW/state",
        payload=payload,
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

    assert mock_publish.called is mqtt_publish
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_config_topic(hass: HomeAssistant) -> None:
    """Test handling of config topic."""

    payload_config = load_json_object_fixture(FIXTURE_PAYLOAD_CONFIG, DOMAIN)

    discovery = MqttServiceInfo(
        subscribed_topic=TOPIC_CONFIG,
        topic=TOPIC_CONFIG,
        payload=json.dumps(payload_config),
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
        payload=_PAYLOAD_DEVICE_STATE,
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


async def test_handle_device_topic_device_not_found(hass: HomeAssistant) -> None:
    """Test handling of device topic when device is not found."""

    payload_config = load_json_object_fixture(FIXTURE_PAYLOAD_CONFIG, DOMAIN)

    discovery = MqttServiceInfo(
        subscribed_topic="cloudapp/QBUSMQTTGW/+/state",
        topic="cloudapp/QBUSMQTTGW/UL2/state",
        payload='{"id":"UL2","properties":{"connected":true},"type":"event"}',
        qos=0,
        retain=False,
        timestamp=time.time(),
    )

    with patch.object(
        QbusConfigCoordinator,
        "async_get_or_request_config",
        return_value=QbusDiscovery(payload_config),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_MQTT}, data=discovery
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_step_user_not_supported(hass: HomeAssistant) -> None:
    """Test user step, which should abort."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"
