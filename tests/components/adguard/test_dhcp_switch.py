"""Tests for the AdGuard Home DHCP switch."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from adguardhome import AdGuardHomeConnectionError, AdGuardHomeError, DhcpConfig
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_ID = "switch.adguard_home_dhcp_server"


@pytest.fixture
def platforms() -> list[Platform]:
    """Set up only the switch platform."""
    return [Platform.SWITCH]


@pytest.mark.parametrize(
    ("enabled", "expected"), [(True, STATE_ON), (False, STATE_OFF)]
)
async def test_dhcp_state(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    enabled: bool,
    expected: str,
) -> None:
    """Expose the configured DHCP state."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, dhcp_available=True
    )
    mock_adguard.dhcp.config.return_value = DhcpConfig(enabled=enabled)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("service", "method", "enabled", "expected"),
    [("turn_on", "enable", True, STATE_ON), ("turn_off", "disable", False, STATE_OFF)],
)
async def test_dhcp_control(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
    enabled: bool,
    expected: str,
) -> None:
    """Call the DHCP action and refresh its observed state."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, dhcp_available=True
    )
    mock_adguard.dhcp.config.return_value = DhcpConfig(enabled=not enabled)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_adguard.dhcp.config.return_value = DhcpConfig(enabled=enabled)

    await hass.services.async_call(
        "switch", service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    getattr(mock_adguard.dhcp, method).assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("service", "method"), [("turn_on", "enable"), ("turn_off", "disable")]
)
async def test_dhcp_control_error(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Report failed DHCP actions without assuming a state change."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, dhcp_available=True
    )
    mock_adguard.dhcp.config.return_value = DhcpConfig(enabled=False)
    getattr(mock_adguard.dhcp, method).side_effect = AdGuardHomeError("error")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch", service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_dhcp_unavailable_and_recovery(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep other controls available and recover DHCP after a read error."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, dhcp_available=True
    )
    mock_adguard.dhcp.config.side_effect = AdGuardHomeConnectionError("offline")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    dhcp_state = hass.states.get(ENTITY_ID)
    assert dhcp_state is not None
    assert dhcp_state.state == STATE_UNAVAILABLE
    protection_state = hass.states.get("switch.adguard_home_protection")
    assert protection_state is not None
    assert protection_state.state == STATE_ON

    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, protection_enabled=False
    )
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.is_state("switch.adguard_home_protection", STATE_OFF)
    assert hass.states.is_state(ENTITY_ID, STATE_UNAVAILABLE)

    mock_adguard.dhcp.config.side_effect = None
    mock_adguard.dhcp.config.return_value = DhcpConfig(enabled=True)
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    dhcp_state = hass.states.get(ENTITY_ID)
    assert dhcp_state is not None
    assert dhcp_state.state == STATE_ON


async def test_dhcp_unsupported(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Do not query DHCP on platforms without support."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, dhcp_available=False
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    mock_adguard.dhcp.config.assert_not_called()
