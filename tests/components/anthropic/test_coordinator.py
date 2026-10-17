"""Tests for the Anthropic integration."""

import asyncio
import datetime as dt
from typing import Literal
from unittest.mock import AsyncMock, call, patch

from anthropic import APITimeoutError, AuthenticationError, RateLimitError
from anthropic.pagination import AsyncPage
from anthropic.types import ModelInfo
from freezegun.api import FrozenDateTimeFactory
from httpx2 import URL, Request, Response
import pytest

from homeassistant.components import conversation
from homeassistant.components.anthropic.const import DOMAIN
from homeassistant.components.anthropic.coordinator import (
    UPDATE_INTERVAL_CONNECTED,
    UPDATE_INTERVAL_DISCONNECTED,
    AnthropicCoordinator,
    model_alias,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import create_content_block, model_list

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


@pytest.mark.freeze_time("2026-10-16T12:00:00Z")
@pytest.mark.parametrize(
    ("model_id", "cached_id", "deprecated_id"),
    [
        pytest.param(
            "claude-haiku-5-5-20261007",
            "claude-haiku-5-5-20261007",
            "claude-haiku-5-5-20261007",
            id="exact_model",
        ),
        pytest.param(
            "claude-haiku-5-5",
            "claude-haiku-5-5-20261007",
            "claude-haiku-5-5",
            id="requested_alias_listed",
        ),
        pytest.param(
            "claude-haiku-5-5",
            "claude-haiku-5-5-20261007",
            "claude-haiku-5-5-20261007",
            id="cached_version_listed",
        ),
        pytest.param(
            "claude-haiku-5-5-20261007",
            "claude-haiku-5-5",
            "claude-haiku-5-5-20261007",
            id="requested_version_listed",
        ),
    ],
)
@pytest.mark.parametrize(
    ("sdk_date", "lifecycle", "retires_at"),
    [
        pytest.param(
            "November 1st, 2026",
            "deprecated",
            dt.datetime(2026, 11, 1, tzinfo=dt.UTC),
            id="ordinal_first_future",
        ),
        pytest.param(
            "January 2nd, 2026",
            "retired",
            dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
            id="ordinal_second_past",
        ),
        pytest.param(
            "January 3rd, 2027",
            "deprecated",
            dt.datetime(2027, 1, 3, tzinfo=dt.UTC),
            id="ordinal_third_future",
        ),
        pytest.param(
            "October 16th, 2026",
            "retired",
            dt.datetime(2026, 10, 16, tzinfo=dt.UTC),
            id="ordinal_today",
        ),
        pytest.param(
            "2027-01-03",
            "deprecated",
            dt.datetime(2027, 1, 3, tzinfo=dt.UTC),
            id="iso_future",
        ),
        pytest.param(
            "2026-01-02",
            "retired",
            dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
            id="iso_past",
        ),
        pytest.param(
            "2026-10-16",
            "retired",
            dt.datetime(2026, 10, 16, tzinfo=dt.UTC),
            id="iso_today",
        ),
        pytest.param(
            "2026-10-16T13:00:00+00:00",
            "deprecated",
            dt.datetime(2026, 10, 16, 13, tzinfo=dt.UTC),
            id="iso_timestamp_future",
        ),
        pytest.param(
            "2026-10-16T14:00:00+03:00",
            "retired",
            dt.datetime(2026, 10, 16, 11, tzinfo=dt.UTC),
            id="iso_timestamp_timezone",
        ),
        pytest.param("not a date", "deprecated", None, id="unparseable_date"),
        pytest.param("", "deprecated", None, id="empty_date"),
    ],
)
def test_active_model_sdk_deprecation_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model_id: str,
    cached_id: str,
    deprecated_id: str,
    sdk_date: str,
    lifecycle: str,
    retires_at: dt.datetime | None,
) -> None:
    """Reconcile active API metadata with SDK dates without changing the cache."""
    cached_model = model_list[0].model_copy(update={"id": cached_id}, deep=True)
    original_metadata = cached_model.model_copy(deep=True)
    coordinator = AnthropicCoordinator(hass, mock_config_entry)
    coordinator.async_set_updated_data([cached_model])

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS",
        {deprecated_id: sdk_date},
        clear=True,
    ):
        model_info, found = coordinator.get_model_info(model_id)

    assert found
    assert model_info == original_metadata.model_copy(
        update={"lifecycle": lifecycle, "retires_at": retires_at}
    )
    assert model_info is not cached_model
    assert cached_model == original_metadata
    assert coordinator.data == [original_metadata]


def test_invalid_sdk_retirement_preserves_api_date(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Keep an existing API retirement date when the SDK date cannot be parsed."""
    model = model_list[0].model_copy(
        update={"retires_at": dt.datetime(2027, 1, 1, tzinfo=dt.UTC)}
    )
    coordinator = AnthropicCoordinator(hass, mock_config_entry)
    coordinator.async_set_updated_data([model])

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS",
        {model.id: "not a date"},
        clear=True,
    ):
        model_info, found = coordinator.get_model_info(model.id)

    assert found
    assert model_info == model.model_copy(update={"lifecycle": "deprecated"})
    assert model.lifecycle == "active"


@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param("active", id="active"),
        pytest.param("deprecated", id="deprecated"),
        pytest.param("retired", id="retired"),
    ],
)
def test_model_lifecycle_without_sdk_deprecation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    lifecycle: str,
) -> None:
    """Return API metadata unchanged when the SDK has no deprecation entry."""
    model = model_list[0].model_copy(update={"lifecycle": lifecycle})
    coordinator = AnthropicCoordinator(hass, mock_config_entry)
    coordinator.async_set_updated_data([model])

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS", clear=True
    ):
        model_info, found = coordinator.get_model_info(model.id)

    assert found
    assert model_info is model


@pytest.mark.freeze_time("2026-10-16T12:00:00Z")
@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param("deprecated", id="deprecated"),
        pytest.param("retired", id="retired"),
    ],
)
@pytest.mark.parametrize(
    "sdk_date",
    [
        pytest.param("2020-01-01", id="past_sdk_date"),
        pytest.param("2030-01-01", id="future_sdk_date"),
    ],
)
def test_inactive_api_model_takes_precedence_over_sdk(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    lifecycle: str,
    sdk_date: str,
) -> None:
    """Preserve authoritative API lifecycle and dates over SDK metadata."""
    model = model_list[0].model_copy(
        update={
            "lifecycle": lifecycle,
            "deprecated_at": dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
            "retires_at": dt.datetime(2027, 2, 1, tzinfo=dt.UTC),
        }
    )
    coordinator = AnthropicCoordinator(hass, mock_config_entry)
    coordinator.async_set_updated_data([model])

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS",
        {model.id: sdk_date},
        clear=True,
    ):
        model_info, found = coordinator.get_model_info(model.id)

    assert found
    assert model_info is model


def test_unknown_sdk_deprecated_model_is_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """SDK deprecations do not turn an unknown model into a catalogue match."""
    coordinator = AnthropicCoordinator(hass, mock_config_entry)
    coordinator.async_set_updated_data(model_list)

    with patch.dict(
        "homeassistant.components.anthropic.coordinator.DEPRECATED_MODELS",
        {"unknown-model": "January 1st, 2020"},
        clear=True,
    ):
        model_info, found = coordinator.get_model_info("unknown-model")

    assert not found
    assert model_info.id == "unknown-model"
    assert model_info.lifecycle == "retired"
    assert model_info.retires_at is None


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


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
@pytest.mark.parametrize(
    "lifecycle",
    [
        pytest.param("deprecated", id="deprecated"),
        pytest.param("retired", id="retired"),
    ],
)
async def test_model_lifecycle_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    mock_create_stream: AsyncMock,
    issue_registry: ir.IssueRegistry,
    lifecycle: Literal["deprecated", "retired"],
) -> None:
    """Successful conversations do not postpone catalogue polling or repairs."""
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
    mock_create_stream.return_value = [create_content_block(0, ["Hello"])] * 2

    freezer.tick(dt.timedelta(hours=4))
    async_fire_time_changed(hass, dt_util.utcnow())
    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    freezer.tick(dt.timedelta(hours=4))
    async_fire_time_changed(hass, dt_util.utcnow())
    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert mock_model_list.await_count == 2

    freezer.tick(dt.timedelta(hours=4))
    async_fire_time_changed(hass, dt_util.utcnow())
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
    ("date_field", "event_offset", "extra_requests"),
    [
        pytest.param("deprecated_at", dt.timedelta(hours=-1), 0, id="deprecation_past"),
        pytest.param(
            "deprecated_at", dt.timedelta(), 0, id="deprecation_previous_success"
        ),
        pytest.param(
            "deprecated_at", dt.timedelta(hours=6), 1, id="deprecation_crossed"
        ),
        pytest.param(
            "deprecated_at", UPDATE_INTERVAL_CONNECTED, 1, id="deprecation_current_time"
        ),
        pytest.param(
            "deprecated_at", dt.timedelta(hours=13), 0, id="deprecation_future"
        ),
        pytest.param("retires_at", dt.timedelta(hours=-1), 1, id="retirement_past"),
        pytest.param("retires_at", dt.timedelta(), 1, id="retirement_previous_success"),
        pytest.param("retires_at", dt.timedelta(hours=6), 1, id="retirement_crossed"),
        pytest.param(
            "retires_at", UPDATE_INTERVAL_CONNECTED, 1, id="retirement_current_time"
        ),
        pytest.param("retires_at", dt.timedelta(hours=13), 0, id="retirement_future"),
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
    """Refresh after a crossed deprecation date or any passed retirement date."""
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
async def test_passed_retirement_date_retries_until_model_is_retired(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
) -> None:
    """Retry pending retirement and remove cached retired models on another trigger."""
    active_model = model_list[0]
    updated_active_model = active_model.model_copy(update={"max_tokens": 123456})
    deprecated_model = model_list[1].model_copy(
        update={
            "lifecycle": "deprecated",
            "retires_at": dt_util.utcnow() - dt.timedelta(days=1),
        }
    )
    retired_model = deprecated_model.model_copy(update={"lifecycle": "retired"})
    mock_model_list.side_effect = [
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[deprecated_model], has_more=False),
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[deprecated_model], has_more=False),
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[retired_model], has_more=False),
        AsyncPage(data=[active_model], has_more=False),
        AsyncPage(data=[updated_active_model], has_more=False),
        AsyncPage(data=[], has_more=False),
    ]
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert coordinator.data == [active_model, deprecated_model]

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == [active_model, deprecated_model]

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == [active_model, retired_model]

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == [active_model, retired_model]
    assert mock_model_list.await_count == 7

    freezer.tick(UPDATE_INTERVAL_CONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data == [updated_active_model]
    assert mock_model_list.await_args_list == [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["deprecated", "retired"], timeout=10.0),
    ] * 3 + [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["deprecated", "retired"], timeout=10.0),
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


@pytest.mark.freeze_time("2026-02-27T12:00:00Z")
@pytest.mark.usefixtures("mock_init_component")
async def test_connection_error_handling(
    mock_model_list: AsyncMock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
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

    freezer.tick(dt.timedelta(seconds=20))
    mock_create_stream.side_effect = APITimeoutError(
        request=Request(method="POST", url=URL()),
    )
    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )
    freezer.tick(dt.timedelta(seconds=20))
    mock_create_stream.side_effect = RateLimitError(
        message=None,
        response=Response(status_code=429, request=Request(method="POST", url=URL())),
        body=None,
    )
    await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )

    # Connection recovery keeps the original pending catalogue check.
    freezer.tick(dt.timedelta(seconds=20))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    mock_model_list.assert_awaited_once_with(lifecycle=["active"], timeout=10.0)

    freezer.tick(UPDATE_INTERVAL_CONNECTED - UPDATE_INTERVAL_DISCONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    mock_model_list.assert_awaited_once()

    freezer.tick(UPDATE_INTERVAL_DISCONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert mock_model_list.await_count == 2


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
@pytest.mark.usefixtures("mock_init_component")
async def test_successful_conversation_preserves_queued_catalogue_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_model_list: AsyncMock,
    mock_create_stream: AsyncMock,
) -> None:
    """A healthy connection report does not cancel a queued debounced refresh."""
    mock_model_list.reset_mock()
    mock_create_stream.return_value = [create_content_block(0, ["Hello"])]
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        side_effect=AuthenticationError(
            message="Invalid API key",
            response=Response(
                status_code=401, request=Request(method="POST", url=URL())
            ),
            body=None,
        ),
    ):
        for _ in range(2):
            result = await conversation.async_converse(
                hass,
                "hello",
                None,
                Context(),
                agent_id="conversation.claude_conversation",
            )
            assert result.response.response_type is intent.IntentResponseType.ERROR
    mock_model_list.assert_awaited_once()

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE

    freezer.tick(dt.timedelta(seconds=10))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert mock_model_list.await_args_list == [
        call(lifecycle=["active"], timeout=10.0),
        call(lifecycle=["active"], timeout=10.0),
    ]


@pytest.mark.freeze_time("2026-10-16T00:00:00Z")
@pytest.mark.usefixtures("mock_init_component")
async def test_successful_conversation_preserves_in_flight_catalogue_retry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    mock_create_stream: AsyncMock,
) -> None:
    """Successful messages during a timed-out catalogue retry keep its short interval."""
    coordinator = mock_config_entry.runtime_data
    request_started = asyncio.Event()
    finish_request = asyncio.Event()

    async def timeout_models_list(**_kwargs: object) -> AsyncPage[ModelInfo]:
        request_started.set()
        await finish_request.wait()
        raise APITimeoutError(
            request=Request("GET", "https://api.anthropic.com/v1/models")
        )

    mock_model_list.reset_mock()
    mock_model_list.side_effect = timeout_models_list
    mock_create_stream.return_value = [create_content_block(0, ["Hello"])] * 2
    coordinator.mark_connection_error()

    freezer.tick(UPDATE_INTERVAL_DISCONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    try:
        await request_started.wait()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )
        assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
        assert coordinator.last_update_success
        assert coordinator.update_interval == UPDATE_INTERVAL_DISCONNECTED
    finally:
        finish_request.set()
        await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL_DISCONNECTED
    mock_model_list.assert_awaited_once()
    mock_model_list.side_effect = None
    mock_model_list.return_value = AsyncPage(data=model_list, has_more=False)

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL_DISCONNECTED

    freezer.tick(UPDATE_INTERVAL_DISCONNECTED)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert mock_model_list.await_count == 2
    assert coordinator.last_update_success
    assert coordinator.update_interval == UPDATE_INTERVAL_CONNECTED


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
