"""Test device discovery, presence updates, and YAML migration."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.device_tracker import CONF_CONSIDER_HOME
from homeassistant.components.hitron_coda.api import CannotConnect, InvalidAuth
from homeassistant.components.hitron_coda.const import DOMAIN
from homeassistant.components.hitron_coda.device_tracker import async_get_scanner
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    EntityRegistry,
    async_entries_for_config_entry,
)
from homeassistant.helpers.issue_registry import IssueRegistry

from .const import CONFIG, DEVICES, MAC, NEW_MAC

ENTITY_ID = "device_tracker.phone"

pytestmark = pytest.mark.usefixtures("mock_client")


@pytest.fixture
def consider_home() -> int:
    """Use the legacy default grace period."""
    return 180


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: EntityRegistry,
    consider_home: int,
) -> MockConfigEntry:
    """Set up a router with a client the user has enabled."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_CONSIDER_HOME: consider_home},
    )
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        MAC.lower(),
        config_entry=mock_config_entry,
        suggested_object_id="phone",
        disabled_by=None,
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.mark.parametrize("consider_home", [0])
async def test_presence_and_names(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Update presence and names without replacing the entity's stable identity."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_HOME
    assert state.attributes["mac"] == MAC.lower()
    assert state.attributes["host_name"] == "phone"
    coordinator = setup_integration.runtime_data
    assert coordinator.update_interval == timedelta(seconds=12)

    mock_client.get_devices.return_value = {}
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_NOT_HOME
    assert hass.states.get(ENTITY_ID).attributes["host_name"] == "phone"

    mock_client.get_devices.return_value = {MAC: "renamed-phone"}
    await coordinator.async_refresh()
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_HOME
    assert state.attributes["host_name"] == "renamed-phone"
    assert state.attributes["friendly_name"] == "renamed-phone"
    assert (
        entity_registry.async_get_entity_id("device_tracker", DOMAIN, MAC.lower())
        == ENTITY_ID
    )


@pytest.mark.parametrize(
    "consider_home",
    [pytest.param(30, id="custom"), pytest.param(180, id="legacy-default")],
)
async def test_consider_home(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    consider_home: int,
) -> None:
    """Keep clients home until the grace period since their last sighting expires."""
    coordinator = setup_integration.runtime_data
    mock_client.get_devices.return_value = {}
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_HOME

    freezer.tick(timedelta(seconds=consider_home - 1))
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_HOME

    freezer.tick(timedelta(seconds=1))
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_NOT_HOME


async def test_reconnection_resets_consider_home(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Measure the grace period from the most recent successful sighting."""
    coordinator = setup_integration.runtime_data
    mock_client.get_devices.return_value = {}
    await coordinator.async_refresh()
    freezer.tick(timedelta(seconds=100))
    mock_client.get_devices.return_value = DEVICES.copy()
    await coordinator.async_refresh()

    mock_client.get_devices.return_value = {}
    freezer.tick(timedelta(seconds=100))
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_HOME

    freezer.tick(timedelta(seconds=80))
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_NOT_HOME


async def test_new_devices(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Discover clients on later polls and register each MAC only once."""
    mock_client.get_devices.return_value = {**DEVICES, NEW_MAC: "laptop"}
    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()
    new_entity_id = entity_registry.async_get_entity_id(
        "device_tracker", DOMAIN, NEW_MAC.lower()
    )
    assert new_entity_id == "device_tracker.laptop"
    assert entity_registry.async_get(new_entity_id).disabled_by is not None

    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()
    entries = async_entries_for_config_entry(
        entity_registry, setup_integration.entry_id
    )
    assert len(entries) == 2


async def test_connection_failure_and_recovery(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed scan makes clients unavailable and preserves their last good data."""
    coordinator = setup_integration.runtime_data
    freezer.tick(timedelta(seconds=179))
    mock_client.get_devices.side_effect = CannotConnect("Router unreachable")
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert coordinator.data == DEVICES

    freezer.tick(timedelta(seconds=1))
    mock_client.get_devices.side_effect = None
    mock_client.get_devices.return_value = {}
    await coordinator.async_refresh()
    assert hass.states.get(ENTITY_ID).state == STATE_NOT_HOME


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Request new credentials when the router rejects a poll."""
    mock_client.get_devices.side_effect = InvalidAuth
    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == setup_integration.entry_id


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        pytest.param(CannotConnect, ConfigEntryState.SETUP_RETRY, id="connection"),
        pytest.param(InvalidAuth, ConfigEntryState.SETUP_ERROR, id="credentials"),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    error: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Do not create trackers when the initial request fails."""
    mock_config_entry.add_to_hass(hass)
    mock_client.get_devices.side_effect = error
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected_state
    assert not hass.states.async_all("device_tracker")


async def test_unload(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Stop polling and mark registered entities unavailable when unloading."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    mock_client.get_devices.reset_mock()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_client.get_devices.assert_not_called()


async def test_registered_client_absent_at_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Restore an enabled tracker even when its client is away on startup or reload."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "device_tracker",
        DOMAIN,
        MAC.lower(),
        config_entry=mock_config_entry,
        suggested_object_id="phone",
        original_name="phone",
        disabled_by=None,
    )
    mock_client.get_devices.return_value = {}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_NOT_HOME
    assert hass.states.get(ENTITY_ID).attributes["host_name"] == "phone"

    mock_client.get_devices.return_value = DEVICES.copy()
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_HOME
    assert (
        len(async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id))
        == 1
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_client.get_devices.return_value = {}
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_NOT_HOME


async def test_legacy_scanner(
    hass: HomeAssistant,
    mock_client: MagicMock,
    issue_registry: IssueRegistry,
) -> None:
    """Keep legacy devices updated and request manual migration without importing."""
    scanner = await async_get_scanner(hass, {"device_tracker": CONFIG})
    assert scanner is not None
    assert await hass.async_add_executor_job(scanner.scan_devices) == [MAC]
    assert scanner.get_device_name(MAC) == "phone"
    mock_client.get_devices.return_value = {}
    assert await hass.async_add_executor_job(scanner.scan_devices) == []
    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"
    assert issue.breaks_in_ha_version == "2027.5.0"


@pytest.mark.parametrize("error", [CannotConnect, InvalidAuth])
async def test_legacy_scanner_update_failure(
    hass: HomeAssistant,
    mock_client: MagicMock,
    error: type[Exception],
) -> None:
    """Do not lose legacy device names when a subsequent scan fails."""
    scanner = await async_get_scanner(hass, {"device_tracker": CONFIG})
    assert scanner is not None
    mock_client.get_devices.side_effect = error
    assert await hass.async_add_executor_job(scanner.scan_devices) == [MAC]
    assert scanner.get_device_name(MAC) == "phone"


@pytest.mark.parametrize("error", [CannotConnect, InvalidAuth])
async def test_legacy_scanner_setup_failure(
    hass: HomeAssistant,
    mock_client: MagicMock,
    issue_registry: IssueRegistry,
    error: type[Exception],
) -> None:
    """Show the migration repair even when the legacy router is unreachable."""
    mock_client.get_devices.side_effect = error
    assert await async_get_scanner(hass, {"device_tracker": CONFIG}) is None
    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is not None
