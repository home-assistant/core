"""Test the DoorBird config flow."""

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.config_entries import ConfigEntryState

from .conftest import MockDoorbirdEntry


async def test_basic_setup(
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.LOADED


async def test_auth_fails(
    doorbird_mocker: Callable[[], Coroutine[Any, Any, MockDoorbirdEntry]],
) -> None:
    """Test basic setup."""
    doorbird_entry = await doorbird_mocker()
    entry = doorbird_entry.entry
    assert entry.state is ConfigEntryState.LOADED
