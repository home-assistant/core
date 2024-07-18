"""Test DoorBird init."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import Mock

import aiohttp

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MockDoorbirdEntry


async def test_basic_setup(
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.LOADED


async def test_auth_fails(
    hass: HomeAssistant,
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker(
        info_side_effect=aiohttp.ClientResponseError(
            request_info=Mock(), history=Mock(), status=401
        )
    )
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
