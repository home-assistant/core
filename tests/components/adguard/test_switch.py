"""Tests for the AdGuard Home switch entity."""

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, call, patch

from adguardhome import AdGuardHomeAuthenticationError, AdGuardHomeError
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
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, SOURCE_REAUTH
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

SWITCH_KEYS = {
    "protection",
    "filtering",
    "parental",
    "querylog",
    "safebrowsing",
    "safesearch",
}


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SWITCH]


@pytest.fixture
def enabled_switches() -> set[str]:
    """Enable all switches unless a test selects a subset."""
    return SWITCH_KEYS


@pytest.fixture
def mock_config_entry(
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    enabled_switches: set[str],
) -> MockConfigEntry:
    """Disable unselected switches before integration setup."""
    for key in SWITCH_KEYS - enabled_switches:
        entity_registry.async_get_or_create(
            Platform.SWITCH,
            DOMAIN,
            f"{mock_config_entry.entry_id}_{key}",
            disabled_by=er.RegistryEntryDisabler.USER,
        )
    return mock_config_entry


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
    ("enabled_switches", "expected_calls", "updated_fields"),
    [
        pytest.param({"protection"}, [call.status()], ["status"], id="protection"),
        pytest.param(
            {"filtering"}, [call.filtering.config()], ["filtering"], id="filtering"
        ),
        pytest.param(
            {"parental"}, [call.parental.enabled()], ["parental"], id="parental"
        ),
        pytest.param(
            {"querylog"}, [call.querylog.config()], ["query_log"], id="querylog"
        ),
        pytest.param(
            {"safebrowsing"},
            [call.safebrowsing.enabled()],
            ["safe_browsing"],
            id="safebrowsing",
        ),
        pytest.param(
            {"safesearch"}, [call.safesearch.config()], ["safe_search"], id="safesearch"
        ),
        pytest.param(
            {"protection", "parental"},
            [call.status(), call.parental.enabled()],
            ["status", "parental"],
            id="multiple",
        ),
    ],
)
async def test_poll_enabled_switches(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    expected_calls: list[tuple],
    updated_fields: list[str],
) -> None:
    """Update enabled fields while retaining initially fetched inactive data."""
    coordinator = init_integration.runtime_data.state
    initial_data = coordinator.data
    responses = {
        "status": (
            mock_adguard.status,
            replace(initial_data.status, protection_enabled=False),
        ),
        "filtering": (
            mock_adguard.filtering.config,
            replace(initial_data.filtering, enabled=False),
        ),
        "parental": (mock_adguard.parental.enabled, False),
        "query_log": (
            mock_adguard.querylog.config,
            replace(initial_data.query_log, enabled=False),
        ),
        "safe_browsing": (mock_adguard.safebrowsing.enabled, False),
        "safe_search": (
            mock_adguard.safesearch.config,
            replace(initial_data.safe_search, enabled=False),
        ),
    }
    for method, response in responses.values():
        method.return_value = response
    mock_adguard.reset_mock()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_adguard.mock_calls == expected_calls
    assert coordinator.data == replace(
        initial_data, **{field: responses[field][1] for field in updated_fields}
    )


@pytest.mark.parametrize("enabled_switches", [{"protection", "parental"}])
async def test_disable_switch(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stop polling a newly disabled switch without stopping the remaining switch."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{init_integration.entry_id}_parental"
    )
    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    mock_adguard.reset_mock()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_adguard.mock_calls == [call.status()]


@pytest.mark.parametrize("enabled_switches", [{"protection"}])
async def test_enable_switch(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    platforms: list[Platform],
) -> None:
    """Re-enabling a switch fetches fresh state and includes it in later polls."""
    assert init_integration.runtime_data.state.data.parental is True
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{init_integration.entry_id}_parental"
    )
    mock_adguard.parental.enabled.return_value = False
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.async_block_till_done()
    with patch("homeassistant.components.adguard.PLATFORMS", platforms):
        freezer.tick(timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_OFF

    mock_adguard.reset_mock()
    mock_adguard.parental.enabled.return_value = True
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_adguard.mock_calls == [call.status(), call.parental.enabled()]
    assert hass.states.get(entity_id).state == STATE_ON
