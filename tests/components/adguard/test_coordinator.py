"""Regression tests for selective AdGuard Home state polling."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from adguardhome import AdGuardHomeConnectionError, AdGuardHomeResponseError
from awesomeversion import AwesomeVersion
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.components.switch import SERVICE_TURN_OFF
from homeassistant.components.update import ATTR_INSTALLED_VERSION
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

SWITCHES = {
    "protection": "switch.adguard_home_protection",
    "filtering": "switch.adguard_home_filtering",
    "parental": "switch.adguard_home_parental_control",
    "querylog": "switch.adguard_home_query_log",
    "safebrowsing": "switch.adguard_home_safe_browsing",
    "safesearch": "switch.adguard_home_safe_search",
}

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.fixture
def platforms() -> list[Platform]:
    """Test switches unless another platform is explicitly requested."""
    return [Platform.SWITCH]


@pytest.fixture
def enabled_switches() -> set[str]:
    """Enable only protection by default."""
    return {"protection"}


@pytest.fixture
def mock_config_entry(
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    enabled_switches: set[str],
) -> MockConfigEntry:
    """Select enabled switches before the shared setup fixture runs."""
    for key, entity_id in SWITCHES.items():
        entity_registry.async_get_or_create(
            Platform.SWITCH,
            DOMAIN,
            f"{mock_config_entry.entry_id}_{key}",
            suggested_object_id=entity_id.removeprefix("switch."),
            disabled_by=None
            if key in enabled_switches
            else er.RegistryEntryDisabler.USER,
        )
    return mock_config_entry


@pytest.fixture
async def init_integration(
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_adguard: AsyncMock,
) -> MockConfigEntry:
    """Freeze timers before setup; verify and reset the full initial refresh."""
    assert_state_calls(mock_adguard, set(SWITCHES))
    mock_adguard.reset_mock()
    return init_integration


def assert_state_calls(
    client: AsyncMock, enabled: set[str], *, status_calls: int | None = None
) -> None:
    """Check every state endpoint, including those that must not be requested."""
    expected = dict.fromkeys(enabled, 1)
    if status_calls is not None:
        expected["protection"] = status_calls
    for key, method in {
        "protection": client.status,
        "filtering": client.filtering.config,
        "parental": client.parental.enabled,
        "querylog": client.querylog.config,
        "safebrowsing": client.safebrowsing.enabled,
        "safesearch": client.safesearch.config,
    }.items():
        assert method.call_count == method.await_count == expected.get(key, 0), key


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int = 10
) -> None:
    """Process one polling interval, or a specified clock advance."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    "enabled_switches",
    [{key} for key in SWITCHES] + [set(SWITCHES)],
    ids=[*SWITCHES, "all"],
)
async def test_poll_enabled_switches(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
    enabled_switches: set[str],
) -> None:
    """Fetch each enabled switch's endpoint once per cycle and no others."""
    await advance(hass, freezer)
    assert_state_calls(mock_adguard, enabled_switches)


@pytest.mark.parametrize("enabled_switches", [set()])
async def test_empty_contexts(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Empty contexts after initialization must not cause another full fetch."""
    coordinator = init_integration.runtime_data.state
    initial_data = coordinator.data
    remove_listener = coordinator.async_add_listener(lambda: None)
    await advance(hass, freezer)
    remove_listener()
    assert_state_calls(mock_adguard, set())
    assert coordinator.data == initial_data


@pytest.mark.parametrize(
    ("enabled_switches", "platforms", "entity_id", "remaining"),
    [
        pytest.param(
            {"parental"},
            [Platform.SWITCH],
            SWITCHES["parental"],
            set(),
            id="last-switch",
        ),
        pytest.param(
            {"parental", "filtering"},
            [Platform.SWITCH],
            SWITCHES["parental"],
            {"filtering"},
            id="one-of-two-switches",
        ),
        pytest.param(
            set(), [Platform.UPDATE], "update.adguard_home", set(), id="update"
        ),
    ],
)
async def test_disable_entity(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    remaining: set[str],
) -> None:
    """Removing a switch or update entity removes its polling interest."""
    entity_registry.async_update_entity(
        entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    await advance(hass, freezer, 300)
    assert_state_calls(mock_adguard, remaining)
    mock_adguard.update.get.assert_not_awaited()


@pytest.mark.parametrize("enabled_switches", [set()])
async def test_enable_switch(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    platforms: list[Platform],
) -> None:
    """Enabling reloads with current initial state, then resumes selective polling."""
    mock_adguard.parental.enabled.return_value = False
    entity_registry.async_update_entity(SWITCHES["parental"], disabled_by=None)
    await hass.async_block_till_done()
    with patch("homeassistant.components.adguard.PLATFORMS", platforms):
        await advance(hass, freezer, RELOAD_AFTER_UPDATE_DELAY + 1)
    assert_state_calls(mock_adguard, set(SWITCHES))
    assert hass.states.get(SWITCHES["parental"]).state == STATE_OFF
    mock_adguard.reset_mock()
    mock_adguard.parental.enabled.return_value = True
    await advance(hass, freezer)
    assert_state_calls(mock_adguard, {"parental"})
    assert hass.states.get(SWITCHES["parental"]).state == STATE_ON


async def test_action_refreshes_only_status(
    hass: HomeAssistant, mock_adguard: AsyncMock
) -> None:
    """An action immediately fetches and publishes only the relevant state."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, protection_enabled=False
    )
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCHES["protection"]},
        blocking=True,
    )
    assert_state_calls(mock_adguard, {"protection"})
    assert hass.states.get(SWITCHES["protection"]).state == STATE_OFF


@pytest.mark.parametrize("platforms", [[Platform.SWITCH, Platform.UPDATE]])
@pytest.mark.parametrize(
    "error",
    [
        AdGuardHomeConnectionError("offline"),
        AdGuardHomeResponseError("bad response", status=500, body=""),
    ],
)
async def test_poll_failure_and_recovery(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Ignore disabled endpoint errors; retain version data on active failure and recover."""
    mock_adguard.safebrowsing.enabled.side_effect = error
    await advance(hass, freezer)
    assert_state_calls(mock_adguard, {"protection"})
    assert hass.states.get(SWITCHES["protection"]).state == STATE_ON
    mock_adguard.reset_mock()
    mock_adguard.status.side_effect = error
    await advance(hass, freezer)
    assert_state_calls(mock_adguard, {"protection"})
    assert hass.states.get(SWITCHES["protection"]).state == STATE_UNAVAILABLE
    update = hass.states.get("update.adguard_home")
    assert update.state == STATE_ON
    assert update.attributes[ATTR_INSTALLED_VERSION] == "v0.107.50"
    mock_adguard.reset_mock()
    mock_adguard.status.side_effect = None
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, version=AwesomeVersion("v0.107.51")
    )
    await advance(hass, freezer)
    assert_state_calls(mock_adguard, {"protection"})
    assert hass.states.get(SWITCHES["protection"]).state == STATE_ON
    update = hass.states.get("update.adguard_home")
    assert update.state == STATE_ON
    assert update.attributes[ATTR_INSTALLED_VERSION] == "v0.107.50"


@pytest.mark.parametrize(
    "platforms", [[Platform.SWITCH, Platform.SENSOR, Platform.UPDATE]]
)
@pytest.mark.parametrize(
    "enabled_switches", [set(), {"protection"}], ids=["update-only", "shared-status"]
)
async def test_update_and_sensor_polling(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
    enabled_switches: set[str],
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Refresh installed version on the update interval without starting switch polling."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, version=AwesomeVersion("v0.107.51")
    )
    await advance(hass, freezer)
    assert_state_calls(mock_adguard, enabled_switches)
    mock_adguard.stats.get.assert_not_awaited()
    mock_adguard.update.get.assert_not_awaited()
    assert (
        hass.states.get("update.adguard_home").attributes[ATTR_INSTALLED_VERSION]
        == "v0.107.50"
    )
    mock_adguard.reset_mock()
    await advance(hass, freezer, 290)
    assert_state_calls(
        mock_adguard, {"protection"}, status_calls=1 + len(enabled_switches)
    )
    mock_adguard.stats.get.assert_awaited_once()
    mock_adguard.update.get.assert_awaited_once()
    assert (
        hass.states.get("update.adguard_home").attributes[ATTR_INSTALLED_VERSION]
        == "v0.107.51"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    assert device.sw_version == "v0.107.51"


@pytest.mark.parametrize(
    ("enabled_switches", "platforms", "seconds"),
    [
        pytest.param({"protection"}, [Platform.SWITCH], 10, id="switch-refresh"),
        pytest.param(set(), [Platform.UPDATE], 300, id="update-refresh"),
    ],
)
async def test_diagnostics_after_selective_refresh(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
    seconds: int,
) -> None:
    """A partial refresh preserves diagnostics for every disabled feature."""
    mock_adguard.status.return_value = replace(
        mock_adguard.status.return_value, version=AwesomeVersion("v0.107.51")
    )
    await advance(hass, freezer, seconds)
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert_state_calls(mock_adguard, {"protection"})
    assert diagnostics["status"]["version"] == "v0.107.51"
    assert diagnostics["features"]["filtering"]["enabled"] is True
    assert diagnostics["features"]["parental"] is True
    assert diagnostics["features"]["query_log"]["enabled"] is True
    assert diagnostics["features"]["safe_browsing"] is True
    assert diagnostics["features"]["safe_search"]["enabled"] is True
