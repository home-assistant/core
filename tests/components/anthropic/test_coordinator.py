"""Tests for the Anthropic integration."""

import datetime
from unittest.mock import AsyncMock, patch

from anthropic import APITimeoutError, AuthenticationError, RateLimitError
from freezegun import freeze_time
from httpx import URL, Request, Response

from homeassistant.components import conversation
from homeassistant.components.anthropic.const import DOMAIN
from homeassistant.components.anthropic.coordinator import (
    UPDATE_INTERVAL_CONNECTED,
    UPDATE_INTERVAL_DISCONNECTED,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

from tests.common import MockConfigEntry, async_fire_time_changed


@patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock)
async def test_auth_error_handling(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test reauth after authentication error during conversation."""
    # This is an assumption of the tests, not the main code:
    assert UPDATE_INTERVAL_DISCONNECTED < UPDATE_INTERVAL_CONNECTED

    mock_create_stream.side_effect = mock_model_list.side_effect = AuthenticationError(
        message="Invalid API key",
        response=Response(status_code=403, request=Request(method="POST", url=URL())),
        body=None,
    )

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown", result

    await hass.async_block_till_done()

    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id


@freeze_time("2026-02-27 12:00:00")
@patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock)
async def test_connection_error_handling(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test making entity unavailable on connection error."""
    mock_create_stream.side_effect = APITimeoutError(
        request=Request(method="POST", url=URL()),
    )

    # Check initial state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unknown"

    # Get timeout
    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown", result

    # Check new state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    # Try again
    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    # Check state is still unavailable
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    mock_create_stream.side_effect = RateLimitError(
        message=None,
        response=Response(status_code=429, request=Request(method="POST", url=URL())),
        body=None,
    )

    # Get a different error meaning the connection is restored
    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    # Check state is back to normal
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "2026-02-27T12:00:00+00:00"

    # Verify the background check period
    test_time = datetime.datetime.now(datetime.UTC) + UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    mock_model_list.assert_not_awaited()

    test_time += UPDATE_INTERVAL_CONNECTED - UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    mock_model_list.assert_awaited_once()


@patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock)
async def test_connection_check_reauth(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test authentication error during background availability check."""
    mock_model_list.side_effect = APITimeoutError(
        request=Request(method="POST", url=URL()),
    )

    # Check initial state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unknown"

    # Get timeout
    assert mock_model_list.await_count == 0
    test_time = datetime.datetime.now(datetime.UTC) + UPDATE_INTERVAL_CONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 1

    # Check new state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    mock_model_list.side_effect = AuthenticationError(
        message="Invalid API key",
        response=Response(status_code=403, request=Request(method="POST", url=URL())),
        body=None,
    )

    # Wait for background check to run and fail
    test_time += UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 2

    # Check state is still unavailable
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    # Verify that the background check is not running anymore
    test_time += UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 2

    # Check that a reauth flow has been created
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id


@patch("anthropic.resources.models.AsyncModels.list", new_callable=AsyncMock)
async def test_connection_restore(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    mock_create_stream: AsyncMock,
) -> None:
    """Test background availability check restore on non-connectivity error."""
    mock_create_stream.side_effect = APITimeoutError(
        request=Request(method="POST", url=URL()),
    )

    # Check initial state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unknown"

    # Get timeout
    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    # Check new state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    mock_model_list.side_effect = APITimeoutError(
        request=Request(method="POST", url=URL()),
    )

    # Wait for background check to run and fail
    assert mock_model_list.await_count == 0
    test_time = datetime.datetime.now(datetime.UTC) + UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 1

    # Check state is still unavailable
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    # Now make the background check succeed
    mock_model_list.side_effect = None
    test_time += UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 2

    # Check that state is back to normal since the error is not connectivity related
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state != "unavailable"

    # Verify the background check period
    test_time += UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 2

    test_time += UPDATE_INTERVAL_CONNECTED - UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 3
