"""Test diagnostics for Home Connect."""

from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.home_connect.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
    """Test config entry diagnostics."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await async_get_config_entry_diagnostics(hass, config_entry) == snapshot


@pytest.mark.usefixtures("bypass_throttle")
async def test_async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device config entry diagnostics."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "SIEMENS-HCS02DWH1-6BE58C26DCC1")},
    )

    assert await async_get_device_diagnostics(hass, config_entry, device) == snapshot


@pytest.mark.usefixtures("bypass_throttle")
async def test_async_device_diagnostics_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    get_appliances: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device config entry diagnostics."""
    get_appliances.side_effect = get_all_appliances
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "Random-Device-ID")},
    )

    with pytest.raises(ValueError):
        await async_get_device_diagnostics(hass, config_entry, device)
