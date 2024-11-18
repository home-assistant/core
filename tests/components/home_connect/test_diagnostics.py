"""Test diagnostics for Home Connect."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.home_connect.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import get_all_appliances

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("bypass_throttle")
async def test_async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup and unload."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await async_get_config_entry_diagnostics(hass, config_entry) == snapshot
