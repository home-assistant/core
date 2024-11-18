"""Test diagnostics for Home Connect."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest

from homeassistant.components.home_connect.const import DOMAIN
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
) -> None:
    """Test setup and unload."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)

    devices = hass.data[DOMAIN][config_entry.entry_id].devices

    for device in devices:
        assert device.device_id in diagnostics
        assert device.appliance.status == diagnostics[device.device_id]
