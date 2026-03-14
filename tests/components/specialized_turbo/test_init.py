"""Tests for Specialized Turbo integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.specialized_turbo.const import CONF_PIN, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ADDRESS, MOCK_ADDRESS_FORMATTED

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test successful setup of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_start.return_value = lambda: None

    with patch(
        "homeassistant.components.specialized_turbo.SpecializedTurboCoordinator",
        return_value=mock_coordinator,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is mock_coordinator


async def test_setup_entry_device_not_in_range(hass: HomeAssistant) -> None:
    """Test setup succeeds even when bike is not in BLE range."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_start.return_value = lambda: None

    with patch(
        "homeassistant.components.specialized_turbo.SpecializedTurboCoordinator",
        return_value=mock_coordinator,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_no_pin(hass: HomeAssistant) -> None:
    """Test setup entry without a PIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_start.return_value = lambda: None

    with patch(
        "homeassistant.components.specialized_turbo.SpecializedTurboCoordinator",
        return_value=mock_coordinator,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unloading of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ADDRESS: MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_start.return_value = lambda: None
    mock_coordinator.async_shutdown = AsyncMock()

    with patch(
        "homeassistant.components.specialized_turbo.SpecializedTurboCoordinator",
        return_value=mock_coordinator,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert entry.state is ConfigEntryState.NOT_LOADED
