"""Tests for the ntfy event platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from aiontfy import Event
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyForbiddenError,
    NtfyHTTPError,
    NtfyTimeoutError,
    NtfyUnauthorizedAuthenticationError,
)
from freezegun.api import FrozenDateTimeFactory, freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ntfy.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def event_only() -> AsyncGenerator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.ntfy.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


@pytest.mark.usefixtures("mock_aiontfy")
@freeze_time("2025-09-03T22:00:00.000Z")
async def test_event_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the ntfy event platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("mock_aiontfy")
async def test_event(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test ntfy events."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get("event.mytopic"))
    assert state.state != STATE_UNKNOWN

    assert state.attributes == {
        "actions": [],
        "attachment": None,
        "click": "https://example.com/",
        "content_type": None,
        "entity_picture": "https://example.com/icon.png",
        "event": Event.MESSAGE,
        "event_type": "Title: Hello",
        "event_types": [
            "Title: Hello",
        ],
        "expires": datetime(2025, 3, 29, 5, 58, 46, tzinfo=UTC),
        "friendly_name": "mytopic",
        "icon": "https://example.com/icon.png",
        "id": "h6Y2hKA5sy0U",
        "message": "Hello",
        "priority": 3,
        "tags": [
            "octopus",
        ],
        "time": datetime(2025, 3, 28, 17, 58, 46, tzinfo=UTC),
        "title": "Title",
        "topic": "mytopic",
    }


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            NtfyHTTPError(41801, 418, "I'm a teapot", ""),
            STATE_UNAVAILABLE,
        ),
        (
            NtfyConnectionError,
            STATE_UNAVAILABLE,
        ),
        (
            NtfyTimeoutError,
            STATE_UNAVAILABLE,
        ),
        (
            NtfyUnauthorizedAuthenticationError(40101, 401, "unauthorized"),
            STATE_UNAVAILABLE,
        ),
        (
            NtfyForbiddenError(403, 403, "forbidden"),
            STATE_UNAVAILABLE,
        ),
        (
            asyncio.CancelledError,
            STATE_UNAVAILABLE,
        ),
        (
            asyncio.InvalidStateError,
            STATE_UNKNOWN,
        ),
        (
            ValueError,
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_event_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
    expected_state: str,
) -> None:
    """Test ntfy events exceptions."""
    mock_aiontfy.subscribe.side_effect = exception

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("event.mytopic"))
    assert state.state == expected_state


async def test_event_topic_protected(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test ntfy events cannot subscribe to protected topic."""
    mock_aiontfy.subscribe.side_effect = NtfyForbiddenError(403, 403, "forbidden")

    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "repairs", {})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("event.mytopic"))
    assert state.state == STATE_UNAVAILABLE

    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id="topic_protected_mytopic"
    )

    await async_process_repairs_platforms(hass)
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, "topic_protected_mytopic")

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"

    assert (entity := entity_registry.async_get("event.mytopic"))
    assert entity.disabled
    assert entity.disabled_by is er.RegistryEntryDisabler.USER
