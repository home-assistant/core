"""Tests for the Lyngdorf select platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import notify_receiver_update

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the select platform."""
    return [Platform.SELECT]


ROOM_PERFECT_ENTITY_ID = "select.mock_lyngdorf_roomperfect_position"
VOICING_ENTITY_ID = "select.mock_lyngdorf_voicing"


async def test_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_room_perfect_select_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting a RoomPerfect position."""
    mock_receiver.room_perfect_position = "focus"
    mock_receiver.room_perfect_positions = ["focus", "global"]

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: ROOM_PERFECT_ENTITY_ID,
            ATTR_OPTION: "global",
        },
        blocking=True,
    )

    mock_receiver.set_room_perfect_position.assert_called_once_with("global")


async def test_select_option_awaits_an_awaitable_setter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test a setter that returns a coroutine is awaited rather than dropped."""
    mock_receiver.set_voicing = AsyncMock()
    mock_receiver.voicing = "Neutral"
    mock_receiver.voicings = ["Neutral", "Music", "Movie"]
    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: VOICING_ENTITY_ID, ATTR_OPTION: "Music"},
        blocking=True,
    )

    mock_receiver.set_voicing.assert_awaited_once_with("Music")


async def test_voicing_select_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test selecting a voicing."""
    mock_receiver.voicing = "Neutral"
    mock_receiver.voicings = ["Neutral", "Music", "Movie"]

    notify_receiver_update(mock_receiver)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: VOICING_ENTITY_ID,
            ATTR_OPTION: "Movie",
        },
        blocking=True,
    )

    mock_receiver.set_voicing.assert_called_once_with("Movie")
