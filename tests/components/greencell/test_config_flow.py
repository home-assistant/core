"""Test cases for the Greencell EVSE config flow in Home Assistant."""

import asyncio
import json

import pytest

from homeassistant.components import mqtt
from homeassistant.components.greencell import config_flow
from homeassistant.components.greencell.config_flow import EVSEConfigFlow
from homeassistant.components.greencell.const import GREENCELL_BROADCAST_TOPIC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_SERIAL_NUMBER, DummyMessage


async def fake_wait_for(coro, timeout):
    """Fake asyncio.wait_for that raises TimeoutError."""
    raise TimeoutError


@pytest.fixture
def fast_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make discovery timeout instant by mocking the DISCOVERY_TIMEOUT constant."""

    # Set DISCOVERY_TIMEOUT to 0 for instant tests
    monkeypatch.setattr(config_flow, "DISCOVERY_TIMEOUT", 0)


@pytest.mark.asyncio
async def test_config_flow_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    stub_mqtt_and_publish,
    hass: HomeAssistant,
    fast_discovery,
) -> None:
    """Happy path: user step creates a valid config entry."""

    flow = EVSEConfigFlow()
    flow.hass = hass

    # Mock MQTT is_connected to return True
    monkeypatch.setattr(mqtt, "is_connected", lambda h: True)

    # Mock mqtt.async_subscribe to simulate a successful discovery
    async def fake_subscribe(h, topic, cb):
        """Fake async_subscribe that simulates a discovery message."""
        asyncio.get_event_loop().call_soon(
            lambda: cb(DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER})))
        )
        return lambda: None

    # Mock mqtt.async_publish
    async def fake_publish(h, topic, payload, qos, retain):
        """Fake async_publish that records published messages."""
        if not hasattr(h, "published"):
            h.published = []
        h.published.append((topic, payload, qos, retain))

    monkeypatch.setattr(mqtt, "async_subscribe", fake_subscribe)
    monkeypatch.setattr(mqtt, "async_publish", fake_publish)

    # Mock async_set_unique_id and _abort_if_unique_id_configured
    async def fake_async_set_unique_id(self, unique_id=None, **kwargs):
        """Fake async_set_unique_id that does nothing."""
        return

    monkeypatch.setattr(
        EVSEConfigFlow,
        "async_set_unique_id",
        fake_async_set_unique_id,
    )

    monkeypatch.setattr(
        EVSEConfigFlow, "_abort_if_unique_id_configured", lambda self: None
    )

    result = await flow.async_step_user(user_input=None)

    assert TEST_SERIAL_NUMBER in result["title"]
    assert result["data"] == {"serial_number": TEST_SERIAL_NUMBER}

    publishes = getattr(hass, "published", [])
    assert any(
        topic == GREENCELL_BROADCAST_TOPIC
        and json.loads(payload) == {"name": "BROADCAST"}
        for topic, payload, qos, retain in publishes
    ), "Expected a broadcast to GREENCELL_BROADCAST_TOPIC"


@pytest.mark.asyncio
async def test_config_flow_duplicate_device(
    stub_mqtt_and_publish,
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    fast_discovery,
) -> None:
    """If device already configured, flow aborts with AbortFlow."""

    flow = EVSEConfigFlow()
    flow.hass = hass

    # Mock MQTT is_connected to return True
    monkeypatch.setattr(mqtt, "is_connected", lambda h: True)

    # Mock mqtt.async_subscribe to simulate a successful discovery
    async def fake_subscribe(h, topic, cb):
        """Fake async_subscribe that simulates a discovery message."""
        asyncio.get_event_loop().call_soon(
            lambda: cb(DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER})))
        )
        return lambda: None

    # Mock mqtt.async_publish
    async def fake_publish(h, topic, payload, qos, retain):
        """Fake async_publish that does nothing."""
        return

    monkeypatch.setattr(mqtt, "async_subscribe", fake_subscribe)
    monkeypatch.setattr(mqtt, "async_publish", fake_publish)

    # Mock async_set_unique_id
    async def fake_set_unique(self, unique_id=None, **kwargs):
        """Fake async_set_unique_id that does nothing."""
        return

    monkeypatch.setattr(EVSEConfigFlow, "async_set_unique_id", fake_set_unique)

    # Mock _abort_if_unique_id_configured to raise AbortFlow
    def abort_configured(self):
        raise AbortFlow("already_configured")

    monkeypatch.setattr(
        EVSEConfigFlow,
        "_abort_if_unique_id_configured",
        abort_configured,
    )

    with pytest.raises(AbortFlow):
        await flow.async_step_user(user_input=None)


@pytest.mark.asyncio
async def test_config_flow_subscription_failure(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant, fast_discovery
) -> None:
    """If MQTT subscribe fails, flow aborts with mqtt_subscription_failed."""
    flow = EVSEConfigFlow()
    flow.hass = hass

    # Mock MQTT is_connected to return True
    monkeypatch.setattr(mqtt, "is_connected", lambda h: True)

    async def fake_subscribe(h, topic, cb):
        """Fake async_subscribe that raises HomeAssistantError."""
        raise HomeAssistantError("fail subscribe")

    monkeypatch.setattr(mqtt, "async_subscribe", fake_subscribe)
    result = await flow.async_step_user(user_input=None)
    assert result["reason"] == "mqtt_subscription_failed"


@pytest.mark.asyncio
async def test_config_flow_discovery_timeout(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant, fast_discovery
) -> None:
    """If no discovery message arrives, flow aborts with discovery_timeout."""
    flow = EVSEConfigFlow()
    flow.hass = hass

    # Mock MQTT is_connected to return True
    monkeypatch.setattr(mqtt, "is_connected", lambda h: True)

    unsub_funcs = []

    async def fake_subscribe(h, topic, cb):
        """Fake async_subscribe that doesn't trigger any callbacks."""
        unsub_funcs.append(lambda: None)
        return unsub_funcs[-1]

    async def fake_publish(h, topic, payload, qos, retain):
        pass

    monkeypatch.setattr(mqtt, "async_subscribe", fake_subscribe)
    monkeypatch.setattr(mqtt, "async_publish", fake_publish)

    res = await flow.async_step_user(user_input=None)
    assert res["reason"] == "no_discovery_data"


@pytest.mark.asyncio
async def test_config_flow_invalid_discovery_payload(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant, fast_discovery
) -> None:
    """If discovery payload missing id, flow aborts with invalid_discovery_data."""
    flow = EVSEConfigFlow()
    flow.hass = hass

    # Mock MQTT is_connected to return True
    monkeypatch.setattr(mqtt, "is_connected", lambda h: True)

    async def fake_publish(h, topic, payload, qos, retain):
        """Fake async_publish that does nothing."""

    async def fake_subscribe(h, topic, cb):
        """Fake async_subscribe that simulates a message with invalid payload."""
        asyncio.get_event_loop().call_soon(
            lambda: cb(DummyMessage(payload=json.dumps({"foo": "bar"})))
        )
        return lambda: None

    monkeypatch.setattr(mqtt, "async_subscribe", fake_subscribe)
    monkeypatch.setattr(mqtt, "async_publish", fake_publish)
    res = await flow.async_step_user(user_input=None)
    assert res["reason"] == "no_discovery_data"
