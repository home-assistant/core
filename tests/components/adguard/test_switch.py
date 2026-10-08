"""Tests for the AdGuard Home switch entity."""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

from adguardhome import AdGuardHomeAuthenticationError, AdGuardHomeError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard switch platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: f"switch.adguard_home_{switch_name}"},
        blocking=True,
    )

    call_assertion(mock_adguard)


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
