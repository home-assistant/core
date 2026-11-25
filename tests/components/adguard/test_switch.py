"""Tests for the AdGuard Home switch entity."""

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from adguardhome import (
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeError,
    DhcpConfig,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


DHCP_ENTITY_ID = "switch.adguard_home_dhcp_server"


@pytest.mark.usefixtures("init_integration", "entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard switch platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("switch_name", "service", "call_assertion"),
    [
        (
            "protection",
            SERVICE_TURN_ON,
            lambda mock: mock.enable_protection.assert_called_once(),
        ),
        (
            "protection",
            SERVICE_TURN_OFF,
            lambda mock: mock.disable_protection.assert_called_once(),
        ),
        (
            "parental_control",
            SERVICE_TURN_ON,
            lambda mock: mock.parental.enable.assert_called_once(),
        ),
        (
            "parental_control",
            SERVICE_TURN_OFF,
            lambda mock: mock.parental.disable.assert_called_once(),
        ),
        (
            "safe_search",
            SERVICE_TURN_ON,
            lambda mock: mock.safesearch.enable.assert_called_once(),
        ),
        (
            "safe_search",
            SERVICE_TURN_OFF,
            lambda mock: mock.safesearch.disable.assert_called_once(),
        ),
        (
            "safe_browsing",
            SERVICE_TURN_ON,
            lambda mock: mock.safebrowsing.enable.assert_called_once(),
        ),
        (
            "safe_browsing",
            SERVICE_TURN_OFF,
            lambda mock: mock.safebrowsing.disable.assert_called_once(),
        ),
        (
            "filtering",
            SERVICE_TURN_ON,
            lambda mock: mock.filtering.enable.assert_called_once(),
        ),
        (
            "filtering",
            SERVICE_TURN_OFF,
            lambda mock: mock.filtering.disable.assert_called_once(),
        ),
        (
            "query_log",
            SERVICE_TURN_ON,
            lambda mock: mock.querylog.enable.assert_called_once(),
        ),
        (
            "query_log",
            SERVICE_TURN_OFF,
            lambda mock: mock.querylog.disable.assert_called_once(),
        ),
    ],
)
async def test_switch_actions(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    switch_name: str,
    service: str,
    call_assertion: Callable[[AsyncMock], Any],
) -> None:
    """Test the adguard switch actions."""
    mock_adguard.status.reset_mock()

    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: f"switch.adguard_home_{switch_name}"},
        blocking=True,
    )

    call_assertion(mock_adguard)

    # The new state is fetched right away, instead of on the next poll.
    mock_adguard.status.assert_called_once()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "expected_message"),
    [
        (
            SERVICE_TURN_ON,
            "An error occurred while turning on AdGuard Home switch",
        ),
        (
            SERVICE_TURN_OFF,
            "An error occurred while turning off AdGuard Home switch",
        ),
    ],
)
async def test_switch_action_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    service: str,
    expected_message: str,
) -> None:
    """Test the adguard switch actions."""
    mock_adguard.enable_protection.side_effect = AdGuardHomeError("Boom")
    mock_adguard.disable_protection.side_effect = AdGuardHomeError("Boom")

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            "switch",
            service,
            {ATTR_ENTITY_ID: "switch.adguard_home_protection"},
            blocking=True,
        )


async def test_switch_authentication_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test credentials rejected while running make the switch ask for new ones."""
    mock_adguard.parental.enabled.side_effect = AdGuardHomeAuthenticationError("Nope")

    await async_update_entity(hass, "switch.adguard_home_parental_control")
    await hass.async_block_till_done()

    state = hass.states.get("switch.adguard_home_parental_control")
    assert state
    assert state.state == STATE_UNAVAILABLE

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


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

    state = hass.states.get(DHCP_ENTITY_ID)
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
        "switch", service, {ATTR_ENTITY_ID: DHCP_ENTITY_ID}, blocking=True
    )

    getattr(mock_adguard.dhcp, method).assert_awaited_once()
    state = hass.states.get(DHCP_ENTITY_ID)
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
            "switch", service, {ATTR_ENTITY_ID: DHCP_ENTITY_ID}, blocking=True
        )
    state = hass.states.get(DHCP_ENTITY_ID)
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
    dhcp_state = hass.states.get(DHCP_ENTITY_ID)
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
    assert hass.states.is_state(DHCP_ENTITY_ID, STATE_UNAVAILABLE)

    mock_adguard.dhcp.config.side_effect = None
    mock_adguard.dhcp.config.return_value = DhcpConfig(enabled=True)
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    dhcp_state = hass.states.get(DHCP_ENTITY_ID)
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

    assert hass.states.get(DHCP_ENTITY_ID) is None
    mock_adguard.dhcp.config.assert_not_called()
