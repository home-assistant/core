"""Test DoorBird init."""

import pytest

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import mock_not_found_exception, mock_unauthorized_exception
from .conftest import DoorbirdMockerType


async def test_basic_setup(
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.LOADED


async def test_auth_fails(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test basic setup with an auth failure."""
    doorbird_entry = await doorbird_mocker(
        info_side_effect=mock_unauthorized_exception()
    )
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    "side_effect",
    [OSError, mock_not_found_exception()],
)
async def test_http_info_request_fails(
    doorbird_mocker: DoorbirdMockerType, side_effect: Exception
) -> None:
    """Test basic setup with an http failure."""
    doorbird_entry = await doorbird_mocker(info_side_effect=side_effect)
    assert doorbird_entry.entry.state is ConfigEntryState.SETUP_RETRY


async def test_http_favorites_request_fails(
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test basic setup with an http failure."""
    doorbird_entry = await doorbird_mocker(
        favorites_side_effect=mock_not_found_exception()
    )
    assert doorbird_entry.entry.state is ConfigEntryState.SETUP_RETRY


async def test_http_schedule_api_missing(
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test missing the schedule API is non-fatal as not all models support it."""
    doorbird_entry = await doorbird_mocker(
        schedule_side_effect=mock_not_found_exception()
    )
    assert doorbird_entry.entry.state is ConfigEntryState.LOADED


async def test_events_changed(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.LOADED
    api = doorbird_entry.api
    api.favorites.reset_mock()
    api.change_favorite.reset_mock()
    api.schedule.reset_mock()

    hass.config_entries.async_update_entry(entry, options={"events": ["xyz"]})
    await hass.async_block_till_done()
    assert len(api.favorites.mock_calls) == 2
    assert len(api.schedule.mock_calls) == 1

    assert len(api.change_favorite.mock_calls) == 1
    favorite_type, title, url = api.change_favorite.mock_calls[0][1]
    assert favorite_type == "http"
    assert title == "Home Assistant (mydoorbird_xyz)"
    assert url == (
        f"http://10.10.10.10:8123/api/doorbird/mydoorbird_xyz?token={entry.entry_id}"
    )
