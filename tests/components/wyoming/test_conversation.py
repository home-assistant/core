"""Test tts."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.handle import Handled, NotHandled
from wyoming.intent import Entity, Intent, NotRecognized

from homeassistant.components import conversation
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.setup import async_setup_component

from . import MockAsyncTcpClient

from tests.common import async_mock_service


@pytest.fixture
async def init_components(hass: HomeAssistant):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


async def test_intent_recognized(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_intent,
    intent_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    test_light = entity_registry.async_get_or_create("light", "demo", "1234")
    hass.states.async_set(
        test_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "test light"}
    )
    calls = async_mock_service(hass, "light", "turn_on")

    intent_events = [
        Intent(
            name="HassTurnOn",
            entities=[Entity(name="name", value="test light")],
            text="Turned on light",
        ).event()
    ]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(intent_events),
    ) as mock_client:
        result = await conversation.async_converse(
            hass,
            "Turn on test light",
            conversation_id=None,
            context=Context(),
            agent_id=intent_config_entry.entry_id,
        )
        assert len(calls) == 1
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.speech == {
            "plain": {"speech": "Turned on light", "extra_data": None}
        }

    assert mock_client.written == snapshot


async def test_intent_not_recognized(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_intent,
    intent_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    intent_events = [NotRecognized("I don't understand").event()]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(intent_events),
    ) as mock_client:
        result = await conversation.async_converse(
            hass,
            "You won't understand this",
            conversation_id=None,
            context=Context(),
            agent_id=intent_config_entry.entry_id,
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH
        )

    assert mock_client.written == snapshot


async def test_intent_recognition_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_intent,
    intent_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    intent_events = [Intent(name="NotAnIntent").event()]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(intent_events),
    ) as mock_client, pytest.raises(intent.UnknownIntent):
        await conversation.async_converse(
            hass,
            "Do something unexpected",
            conversation_id=None,
            context=Context(),
            agent_id=intent_config_entry.entry_id,
        )

    assert mock_client.written == snapshot


async def test_intent_recognition_client_dropped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_intent,
    intent_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    intent_events = [None]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(intent_events),
    ) as mock_client:
        result = await conversation.async_converse(
            hass,
            "This will never be recognized",
            conversation_id=None,
            context=Context(),
            agent_id=intent_config_entry.entry_id,
        )

        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert result.response.error_code == intent.IntentResponseErrorCode.UNKNOWN

    assert mock_client.written == snapshot


async def test_intent_handled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_handle,
    handle_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    handle_events = [Handled("Turned on light").event()]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(handle_events),
    ) as mock_client:
        result = await conversation.async_converse(
            hass,
            "Turn on test light",
            conversation_id=None,
            context=Context(),
            agent_id=handle_config_entry.entry_id,
        )
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.speech == {
            "plain": {"speech": "Turned on light", "extra_data": None}
        }

    assert mock_client.written == snapshot


async def test_intent_not_handled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_handle,
    handle_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    handle_events = [NotHandled("I don't understand").event()]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(handle_events),
    ) as mock_client:
        result = await conversation.async_converse(
            hass,
            "You won't understand this",
            conversation_id=None,
            context=Context(),
            agent_id=handle_config_entry.entry_id,
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert (
            result.response.error_code
            == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
        )
        assert result.response.speech == {
            "plain": {"speech": "I don't understand", "extra_data": None}
        }

    assert mock_client.written == snapshot


async def test_intent_handling_client_dropped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_components,
    init_wyoming_handle,
    handle_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test intent recogntion."""
    handle_events = [None]

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(handle_events),
    ) as mock_client:
        result = await conversation.async_converse(
            hass,
            "This will never be handled",
            conversation_id=None,
            context=Context(),
            agent_id=handle_config_entry.entry_id,
        )
        assert result.response.response_type == intent.IntentResponseType.ERROR
        assert result.response.error_code == intent.IntentResponseErrorCode.UNKNOWN

    assert mock_client.written == snapshot
