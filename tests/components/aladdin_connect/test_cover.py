"""Tests for the Aladdin Connect cover platform."""

from unittest.mock import AsyncMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "cover.test_door"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up integration with only the cover platform."""
    with patch("homeassistant.components.aladdin_connect.PLATFORMS", [Platform.COVER]):
        await init_integration(hass, entry)


async def test_cover_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the cover entity states and attributes."""
    await _setup(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_open_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
) -> None:
    """Test opening the cover."""
    await _setup(hass, mock_config_entry)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_aladdin_connect_api.open_door.assert_called_once_with("test_device_id", 1)


async def test_close_cover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
) -> None:
    """Test closing the cover."""
    await _setup(hass, mock_config_entry)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_aladdin_connect_api.close_door.assert_called_once_with("test_device_id", 1)


@pytest.mark.parametrize(
    ("status", "expected_closed", "expected_opening", "expected_closing"),
    [
        ("closed", True, False, False),
        ("open", False, False, False),
        ("opening", False, True, False),
        ("closing", False, False, True),
    ],
)
async def test_cover_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
    status: str,
    expected_closed: bool,
    expected_opening: bool,
    expected_closing: bool,
) -> None:
    """Test cover state properties."""
    mock_aladdin_connect_api.get_doors.return_value[0].status = status
    await _setup(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert (state.state == "closed") == expected_closed
    assert (state.state == "opening") == expected_opening
    assert (state.state == "closing") == expected_closing


async def test_cover_none_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
) -> None:
    """Test cover state when status is None."""
    mock_aladdin_connect_api.get_doors.return_value[0].status = None
    await _setup(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"


async def test_cover_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover becomes unavailable when coordinator update fails."""
    await _setup(hass, mock_config_entry)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_aladdin_connect_api.get_doors.side_effect = aiohttp.ClientError()
    freezer.tick(15)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
