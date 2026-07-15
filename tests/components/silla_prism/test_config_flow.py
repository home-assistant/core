"""Test the Silla Prism config flow."""

import asyncio
import time
from unittest.mock import patch

import pytest

from homeassistant.components.silla_prism.config_flow import (
    _PROBE_TIMEOUT,
    PrismConfigFlow,
)
from homeassistant.components.silla_prism.const import CONF_BASE_TOPIC, DOMAIN
from homeassistant.config_entries import SOURCE_MQTT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import BASE_TOPIC, HELLO_PAYLOAD, HELLO_TOPIC, SERIAL

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient

_PROBE_PATH = (
    "homeassistant.components.silla_prism.config_flow.PrismConfigFlow._async_probe"
)
_MQTT_CLIENT_PATH = (
    "homeassistant.components.silla_prism.config_flow.async_wait_for_mqtt_client"
)


def _discovery(topic: str, payload: str | bytes) -> MqttServiceInfo:
    return MqttServiceInfo(
        subscribed_topic="prism/hello",
        topic=topic,
        payload=payload,
        qos=0,
        retain=True,
        timestamp=time.time(),
    )


async def test_user_flow(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test the user flow succeeds once traffic is seen on the base topic."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    task = hass.async_create_task(
        hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BASE_TOPIC: BASE_TOPIC}
        )
    )
    # Fire repeatedly so a message lands once the probe has subscribed.
    for _ in range(20):
        await asyncio.sleep(0)
        async_fire_mqtt_message(hass, "prism/1/state", "1")
        if task.done():
            break
    result = await task

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silla Prism"
    assert result["data"] == {CONF_BASE_TOPIC: BASE_TOPIC}
    assert result["result"].unique_id == BASE_TOPIC


async def test_user_flow_no_device(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the user flow errors when no traffic is seen."""
    with patch(_PROBE_PATH, return_value=False):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_BASE_TOPIC: BASE_TOPIC},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_device"}


async def test_user_flow_mqtt_unavailable(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the user flow errors when MQTT is not available."""
    with patch(_MQTT_CLIENT_PATH, return_value=False):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_BASE_TOPIC: BASE_TOPIC},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "mqtt_unavailable"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow aborts when the base topic is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_BASE_TOPIC: BASE_TOPIC},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_probe_detects_no_traffic(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the base-topic probe times out when the topic is silent."""
    flow = PrismConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.silla_prism.config_flow._PROBE_TIMEOUT",
        0.01,
    ):
        assert await flow._async_probe(BASE_TOPIC) is False
    assert _PROBE_TIMEOUT == 5


async def test_discovery_flow(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test discovery via the hello topic creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_MQTT},
        data=_discovery(HELLO_TOPIC, HELLO_PAYLOAD),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"serial": SERIAL}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Silla Prism"
    assert result["data"] == {CONF_BASE_TOPIC: BASE_TOPIC}
    assert result["result"].unique_id == BASE_TOPIC


async def test_discovery_already_configured(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discovery aborts when the Prism is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_MQTT},
        data=_discovery(HELLO_TOPIC, HELLO_PAYLOAD),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        ("prism/hello", b""),
        ("prism/state", "1"),
        ("prism/hello", "   "),
    ],
    ids=["empty_payload", "not_hello_topic", "unparseable_hello"],
)
async def test_discovery_invalid(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    topic: str,
    payload: str | bytes,
) -> None:
    """Test discovery aborts on invalid discovery information."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_MQTT},
        data=_discovery(topic, payload),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"
