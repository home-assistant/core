"""Greencell integration initialization test cases."""

import asyncio
from collections.abc import Callable
import time
from unittest.mock import patch

from greencell_client.access import GreencellAccess
from greencell_client.elec_data import ElecData3Phase, ElecDataSinglePhase

from homeassistant.components.greencell import make_ready_handler
from homeassistant.components.greencell.const import GREENCELL_DISC_TOPIC
from homeassistant.components.mqtt import ReceiveMessage
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERIAL_NUMBER, TEST_VOLTAGE_TOPIC

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient


def _make_message(topic: str, payload: str) -> ReceiveMessage:
    """Build a ReceiveMessage for handler unit tests."""
    return ReceiveMessage(
        topic=topic,
        payload=payload,
        qos=0,
        retain=False,
        subscribed_topic=topic,
        timestamp=time.time(),
    )


def test_ready_handler_sets_event_on_matching_disc() -> None:
    """Handler sets event when discovery topic payload matches serial."""
    event = asyncio.Event()
    handler = make_ready_handler(TEST_SERIAL_NUMBER, event)

    handler(_make_message(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}'))

    assert event.is_set()


def test_ready_handler_ignores_non_matching_disc() -> None:
    """Handler ignores discovery message for different serial."""
    event = asyncio.Event()
    handler = make_ready_handler(TEST_SERIAL_NUMBER, event)

    handler(_make_message(GREENCELL_DISC_TOPIC, '{"id": "OTHER_SERIAL"}'))

    assert not event.is_set()


def test_ready_handler_sets_event_on_voltage_topic() -> None:
    """Handler sets event when voltage topic receives valid payload."""
    event = asyncio.Event()
    handler = make_ready_handler(TEST_SERIAL_NUMBER, event)

    handler(_make_message(TEST_VOLTAGE_TOPIC, '{"l1": 230}'))

    assert event.is_set()


def test_ready_handler_ignores_invalid_json() -> None:
    """Handler does not set event on malformed payload."""
    event = asyncio.Event()
    handler = make_ready_handler(TEST_SERIAL_NUMBER, event)

    handler(_make_message(TEST_VOLTAGE_TOPIC, "{INVALID JSON}"))

    assert not event.is_set()


def test_ready_handler_noop_when_already_set() -> None:
    """Handler returns early when event already set."""
    event = asyncio.Event()
    event.set()
    handler = make_ready_handler(TEST_SERIAL_NUMBER, event)

    # Would normally be ignored (wrong serial), but we just verify no raise
    handler(_make_message(GREENCELL_DISC_TOPIC, '{"id": "OTHER"}'))

    assert event.is_set()


async def _mock_subscribe_fires(messages: list[tuple[str, str]]):
    """Return a mock async_subscribe that fires given messages on subscription."""

    async def _subscribe(
        hass: HomeAssistant, topic: str, msg_callback, *args, **kwargs
    ) -> Callable[[], None]:
        """Mock async_subscribe that fires given messages on subscription."""
        for msg_topic, payload in messages:
            if msg_topic == topic:
                msg_callback(_make_message(topic, payload))
        return lambda: None

    return _subscribe


async def test_async_setup_entry_ready_via_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds when device responds on discovery topic."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(
        [(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}')]
    )

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=subscribe,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_ready_via_voltage(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup succeeds when device responds on voltage topic."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(
        [(TEST_VOLTAGE_TOPIC, '{"l1": 230, "l2": 230, "l3": 230}')]
    )

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=subscribe,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_creates_runtime_data(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup creates proper runtime_data structure."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(
        [(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}')]
    )

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=subscribe,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    runtime = mock_config_entry.runtime_data
    assert isinstance(runtime.access, GreencellAccess)
    assert isinstance(runtime.current_data, ElecData3Phase)
    assert isinstance(runtime.voltage_data, ElecData3Phase)
    assert isinstance(runtime.power_data, ElecDataSinglePhase)
    assert isinstance(runtime.state_data, ElecDataSinglePhase)


async def test_async_setup_entry_timeout_raises_not_ready(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryNotReady when device doesn't respond in time."""
    mock_config_entry.add_to_hass(hass)

    async def _subscribe_noop(
        hass: HomeAssistant, topic: str, msg_callback, *args, **kwargs
    ) -> Callable[[], None]:
        """Mock async_subscribe that does not fire any messages."""
        return lambda: None

    with (
        patch("homeassistant.components.greencell.DISCOVERY_TIMEOUT", 0),
        patch(
            "homeassistant.components.greencell.mqtt.async_subscribe",
            side_effect=_subscribe_noop,
        ),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_unload_entry_success(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unload entry cleans up platforms."""
    mock_config_entry.add_to_hass(hass)

    subscribe = await _mock_subscribe_fires(
        [(GREENCELL_DISC_TOPIC, f'{{"id": "{TEST_SERIAL_NUMBER}"}}')]
    )

    with patch(
        "homeassistant.components.greencell.mqtt.async_subscribe",
        side_effect=subscribe,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert result is True
