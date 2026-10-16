"""Tests for the Anthropic integration."""

import datetime as dt
from typing import Literal
from unittest.mock import AsyncMock, call, patch

from anthropic import APITimeoutError, AuthenticationError, RateLimitError
from anthropic.pagination import AsyncPage
from anthropic.types import ModelInfo
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
from httpx2 import URL, Request, Response
import pytest

from homeassistant.components import conversation
from homeassistant.components.anthropic.const import DOMAIN
from homeassistant.components.anthropic.coordinator import (
    UPDATE_INTERVAL_CONNECTED,
    UPDATE_INTERVAL_DISCONNECTED,
    model_alias,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import model_list

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("model_id", "expected_alias"),
    [
        pytest.param("claude-opus-4-5-20251101", "claude-opus-4-5", id="dated_model"),
        pytest.param("claude-opus-4-7", "claude-opus-4-7", id="version_alias"),
        pytest.param("claude-opus-5", "claude-opus-5", id="major_version_alias"),
        pytest.param(
            "claude-opus-4-10", "claude-opus-4-10", id="multi_digit_version_alias"
        ),
        pytest.param(
            "claude-mythos-preview", "claude-mythos-preview", id="preview_alias"
        ),
    ],
)
def test_model_alias(model_id: str, expected_alias: str) -> None:
    """Test model aliases preserve versions and remove date suffixes."""
    assert model_alias(model_id) == expected_alias


async def test_model_pagination(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
) -> None:
    """Fetch every page of the active and inactive catalogues."""
    active_models = model_list[:2]
    inactive_models = [
        model_list[2].model_copy(update={"lifecycle": "deprecated"}, deep=True),
        model_list[3].model_copy(update={"lifecycle": "retired"}, deep=True),
    ]
    mock_model_list.side_effect = [
        AsyncPage(data=active_models[:1], has_more=True),
        AsyncPage(data=inactive_models[:1], has_more=True),
    ]
    with (
        patch.object(
            AsyncPage, "has_next_page", side_effect=[True, False, True, False]
        ),
        patch.object(
            AsyncPage,
            "get_next_page",
            side_effect=[
                AsyncPage(data=active_models[1:], has_more=False),
                AsyncPage(data=inactive_models[1:], has_more=False),
            ],
        ) as mock_next_page,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_model_list.await_args_list == [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["deprecated", "retired"], timeout=10.0),
    ]
    assert mock_next_page.await_count == 2
    assert mock_config_entry.runtime_data.data == [*active_models, *inactive_models]


@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param("deprecated", id="deprecated"),
        pytest.param("retired", id="retired"),
    ],
)
async def test_model_lifecycle_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    issue_registry: ir.IssueRegistry,
    lifecycle: Literal["deprecated", "retired"],
) -> None:
    """Create a repair when a model leaves the active catalogue."""
    active_model = model_list[0].model_copy(deep=True)
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        next(iter(mock_config_entry.subentries.values())),
        data={"chat_model": active_model.id},
    )
    mock_model_list.side_effect = [
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[], has_more=False),
        AsyncPage(data=[], has_more=False),
        AsyncPage(
            data=[active_model.model_copy(update={"lifecycle": lifecycle})],
            has_more=False,
        ),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is None

    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL_CONNECTED)
    await hass.async_block_till_done()

    assert (
        mock_model_list.await_args_list
        == [
            call(lifecycle=["active"], timeout=10.0),
            call(lifecycle=["deprecated", "retired"], timeout=10.0),
        ]
        * 2
    )
    assert issue_registry.async_get_issue(DOMAIN, "model_deprecated") is not None


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
async def test_inactive_models_cached_until_active_metadata_changes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
) -> None:
    """Keep inactive metadata between polls and refresh it after an active change."""
    active_model = model_list[0]
    updated_active_model = active_model.model_copy(update={"max_tokens": 123456})
    deprecated_model = model_list[1].model_copy(update={"lifecycle": "deprecated"})
    retired_model = deprecated_model.model_copy(update={"lifecycle": "retired"})
    mock_model_list.side_effect = [
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[deprecated_model], has_more=False),
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[updated_active_model], has_more=False),
        AsyncPage(data=[retired_model], has_more=False),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data == [active_model, deprecated_model]

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == [active_model, deprecated_model]
    assert mock_model_list.await_args_list == [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["deprecated", "retired"], timeout=10.0),
        call(lifecycle=["active"], timeout=10.0),
    ]

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == [updated_active_model, retired_model]
    assert mock_model_list.await_args_list[3:] == [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["deprecated", "retired"], timeout=10.0),
    ]


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
async def test_reactivated_model_replaces_cached_inactive_model(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
) -> None:
    """Remove obsolete inactive metadata when a model becomes active again."""
    active_model = model_list[0]
    reactivated_model = model_list[1]
    retired_model = reactivated_model.model_copy(update={"lifecycle": "retired"})
    mock_model_list.side_effect = [
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[retired_model], has_more=False),
        AsyncPage(data=[active_model, reactivated_model], has_more=False),
        AsyncPage(data=[], has_more=False),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.data == [active_model, reactivated_model]
    assert mock_config_entry.runtime_data.get_model_info(reactivated_model.id) == (
        reactivated_model,
        True,
    )
    assert (
        mock_model_list.await_args_list
        == [
            call(lifecycle=["active"], timeout=10.0),
            call(lifecycle=["deprecated", "retired"], timeout=10.0),
        ]
        * 2
    )


async def test_later_inactive_metadata_takes_precedence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
) -> None:
    """Use the later response when a lifecycle changes between catalogue queries."""
    model = model_list[0]
    deprecated_model = model.model_copy(update={"lifecycle": "deprecated"})
    mock_model_list.side_effect = [
        AsyncPage(data=[model], has_more=False),
        AsyncPage(data=[deprecated_model], has_more=False),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.data == [deprecated_model]
    assert mock_config_entry.runtime_data.get_model_info(model.id) == (
        deprecated_model,
        True,
    )


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
async def test_empty_model_catalogue(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
) -> None:
    """An empty successful catalogue does not refetch inactive models every poll."""
    mock_model_list.side_effect = None
    mock_model_list.return_value = AsyncPage(data=[], has_more=False)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data == []
    assert coordinator.last_update_success

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == []
    assert coordinator.last_update_success
    assert mock_model_list.await_args_list == [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["deprecated", "retired"], timeout=10.0),
        call(lifecycle=["active"], timeout=10.0),
    ]


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
@pytest.mark.parametrize(
    "date_field",
    [
        pytest.param("deprecated_at", id="deprecation"),
        pytest.param("retires_at", id="retirement"),
    ],
)
@pytest.mark.parametrize(
    ("event_offset", "extra_requests"),
    [
        pytest.param(dt.timedelta(hours=-1), 0, id="past"),
        pytest.param(dt.timedelta(), 0, id="previous_success"),
        pytest.param(dt.timedelta(hours=6), 1, id="crossed"),
        pytest.param(UPDATE_INTERVAL_CONNECTED, 1, id="current_time"),
        pytest.param(dt.timedelta(hours=13), 0, id="future"),
    ],
)
async def test_scheduled_lifecycle_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    date_field: str,
    event_offset: dt.timedelta,
    extra_requests: int,
) -> None:
    """Refresh inactive metadata only when a scheduled date has just been crossed."""
    active_model = model_list[0]
    inactive_model = model_list[1].model_copy(
        update={"lifecycle": "deprecated", date_field: dt_util.utcnow() + event_offset}
    )
    mock_model_list.side_effect = [
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[inactive_model], has_more=False),
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[inactive_model], has_more=False),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    mock_model_list.reset_mock()

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.data == [active_model, inactive_model]
    assert mock_model_list.await_args_list == [
        call(lifecycle=["active"], timeout=10.0),
        *[call(lifecycle=["deprecated", "retired"], timeout=10.0)][:extra_requests],
    ]


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
@pytest.mark.parametrize(
    ("active_model", "inactive_model"),
    [
        pytest.param(
            model_list[0].model_copy(update={"max_tokens": 123456}),
            model_list[1].model_copy(update={"lifecycle": "deprecated"}),
            id="active_metadata_changed",
        ),
        pytest.param(
            model_list[0],
            model_list[1].model_copy(
                update={
                    "lifecycle": "deprecated",
                    "retires_at": dt.datetime(2026, 10, 16, 6, tzinfo=dt.UTC),
                }
            ),
            id="scheduled_retirement_crossed",
        ),
    ],
)
async def test_inactive_fetch_failure_retries_without_committing_partial_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    active_model: ModelInfo,
    inactive_model: ModelInfo,
) -> None:
    """Keep the old catalogue and retry inactive changes after an unsuccessful poll."""
    retired_model = inactive_model.model_copy(update={"lifecycle": "retired"})
    mock_model_list.side_effect = [
        AsyncPage(data=[model_list[0]], has_more=False),
        AsyncPage(data=[inactive_model], has_more=False),
        AsyncPage(data=[active_model], has_more=False),
        APITimeoutError(request=Request("GET", "https://api.anthropic.com/v1/models")),
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[retired_model], has_more=False),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL_DISCONNECTED
    assert coordinator.data == [model_list[0], inactive_model]

    freezer.tick(UPDATE_INTERVAL_DISCONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL_CONNECTED
    assert coordinator.data == [active_model, retired_model]
    assert (
        mock_model_list.await_args_list
        == [
            call(lifecycle=["active"], timeout=10.0),
            call(lifecycle=["deprecated", "retired"], timeout=10.0),
        ]
        * 3
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_auth_error_handling(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
) -> None:
    """Test reauth after authentication error during conversation."""
    mock_model_list.reset_mock()
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

    assert result.response.response_type is intent.IntentResponseType.ERROR
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
@pytest.mark.usefixtures("mock_init_component")
async def test_connection_error_handling(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test making entity unavailable on connection error."""
    mock_model_list.reset_mock()
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

    assert result.response.response_type is intent.IntentResponseType.ERROR
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
    test_time = dt_util.utcnow() + UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    mock_model_list.assert_not_awaited()

    test_time += UPDATE_INTERVAL_CONNECTED - UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    mock_model_list.assert_awaited_once()


@pytest.mark.usefixtures("mock_init_component")
async def test_connection_check_reauth(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test authentication error during background availability check."""
    mock_model_list.reset_mock()
    mock_model_list.side_effect = APITimeoutError(
        request=Request(method="POST", url=URL()),
    )

    # Check initial state
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unknown"

    # Get timeout
    assert mock_model_list.await_count == 0
    test_time = dt_util.utcnow() + UPDATE_INTERVAL_CONNECTED
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


@pytest.mark.usefixtures("mock_init_component")
async def test_connection_restore(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test background availability check restore on non-connectivity error."""
    mock_model_list.reset_mock()
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
    test_time = dt_util.utcnow() + UPDATE_INTERVAL_DISCONNECTED
    async_fire_time_changed(hass, test_time)
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 1

    # Check state is still unavailable
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.state == "unavailable"

    # Now make the background check succeed
    mock_model_list.side_effect = None
    mock_model_list.return_value = AsyncPage(data=model_list, has_more=False)
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
