"""Test cases for the Greencell discovery listener setup in Home Assistant."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from homeassistant.components.greencell import (
    CONF_SERIAL_NUMBER,
    GREENCELL_DISC_TOPIC,
    setup_discovery_listener,
)
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERIAL_NUMBER, DummyHass, DummyMessage, ExpectedCallGenerator

# --- Happy-path test for setup_discovery_listener ---


@pytest.mark.asyncio
async def test_setup_discovery_listener_happy_path(
    stub_subscribe, hass: HomeAssistant
) -> None:
    """Happy path: sending QUERY for a newly discovered device."""

    unsubscribe = setup_discovery_listener(hass)

    await asyncio.sleep(0)

    assert len(stub_subscribe) == 1
    topic, callback = stub_subscribe[0]
    assert topic == GREENCELL_DISC_TOPIC

    msg = DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER}))
    callback(msg)

    expected_call = ExpectedCallGenerator.generate_mqtt_publish_cmd(
        json.dumps({"name": "QUERY"}),
    )
    assert expected_call in hass.services.calls

    unsubscribe()
    assert stub_subscribe == []


@pytest.mark.asyncio
async def test_known_device_logs_debug(
    stub_subscribe, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Known device should log debug and not send publish."""

    entry = SimpleNamespace(data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER})
    local_hass = DummyHass(entries=[entry])
    unsubscribe = setup_discovery_listener(local_hass)
    await asyncio.sleep(0)
    topic, callback = stub_subscribe[0]

    caplog.set_level("DEBUG")
    msg = DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER}))
    callback(msg)

    assert "already configured" in caplog.text
    assert local_hass.services.calls == []
    unsubscribe()
    assert stub_subscribe == []


# --- Error cases ---
@pytest.mark.asyncio
async def test_invalid_json_payload(
    stub_subscribe, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid JSON should be logged and not trigger publish."""

    unsubscribe = setup_discovery_listener(hass)
    await asyncio.sleep(0)
    _, callback = stub_subscribe[0]
    msg = DummyMessage(payload="not-a-json")
    caplog.clear()
    caplog.set_level("ERROR")
    callback(msg)
    assert "Invalid JSON" in caplog.text
    assert hass.services.calls == []
    unsubscribe()


@pytest.mark.asyncio
async def test_missing_id_in_payload(
    stub_subscribe, hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """JSON without 'id' key should log warning and not trigger publish."""

    unsubscribe = setup_discovery_listener(hass)
    await asyncio.sleep(0)
    _, callback = stub_subscribe[0]
    msg = DummyMessage(payload=json.dumps({"foo": "bar"}))
    caplog.clear()
    caplog.set_level("WARNING")
    callback(msg)
    assert "without valid 'id'" in caplog.text
    assert hass.services.calls == []
    unsubscribe()


@pytest.mark.asyncio
async def test_known_device_does_not_publish(stub_subscribe) -> None:
    """If device is already configured, no publish should occur."""

    entry = SimpleNamespace(data={CONF_SERIAL_NUMBER: TEST_SERIAL_NUMBER})
    hass = DummyHass(entries=[entry])
    unsubscribe = setup_discovery_listener(hass)
    await asyncio.sleep(0)
    _, callback = stub_subscribe[0]
    msg = DummyMessage(payload=json.dumps({"id": TEST_SERIAL_NUMBER}))
    callback(msg)
    assert hass.services.calls == []
    unsubscribe()
