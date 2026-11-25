"""Tests for the Danfoss Air integration setup and polling."""

from datetime import timedelta
import threading
import time
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pydanfossair.commands import ReadCommand
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.danfoss_air.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from . import setup_integration

YAML_CONFIG = {DOMAIN: {CONF_HOST: "192.0.2.1"}}


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move past the update throttle and update every entity one at a time."""
    freezer.tick(timedelta(seconds=61))
    # Let the scheduled polls that are now due finish first, so they cannot
    # write a state after the updates below.
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for entity_id in hass.states.async_entity_ids():
        await async_update_entity(hass, entity_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def _fetch_count(client: MagicMock) -> int:
    """Return how many fetches have started, counted by their first read."""
    return sum(
        call.args[0] is ReadCommand.exhaustTemperature
        for call in client.command.call_args_list
    )


def _unavailable(hass: HomeAssistant) -> list[str]:
    """Return the entities that are unavailable."""
    return [
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    ]


async def test_unavailable_when_connection_lost(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_danfoss_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entities go unavailable when the CCM is unreachable, and recover."""
    await setup_integration(hass, mock_config_entry)
    await _poll(hass, freezer)
    entity_ids = hass.states.async_entity_ids()
    assert entity_ids
    assert _unavailable(hass) == []

    read_values = mock_danfoss_client.command.side_effect
    mock_danfoss_client.command.side_effect = OSError("No route to host")

    await _poll(hass, freezer)
    assert sorted(_unavailable(hass)) == sorted(entity_ids)
    assert "Lost connection to Danfoss Air CCM module" in caplog.text

    # Only the first failed poll is logged.
    caplog.clear()
    await _poll(hass, freezer)
    assert sorted(_unavailable(hass)) == sorted(entity_ids)
    assert "Lost connection" not in caplog.text

    mock_danfoss_client.command.side_effect = read_values

    await _poll(hass, freezer)
    assert _unavailable(hass) == []
    assert "Connection to Danfoss Air CCM module restored" in caplog.text


HUMIDITY = "sensor.danfoss_air_humidity"
AUTOMATIC_BYPASS = "switch.danfoss_air_automatic_bypass"


@pytest.mark.parametrize(
    ("connected_before", "fetch_fails", "expected"),
    [
        pytest.param(
            True,
            True,
            {HUMIDITY: STATE_UNAVAILABLE, AUTOMATIC_BYPASS: STATE_UNAVAILABLE},
            id="connection-lost",
        ),
        pytest.param(
            False,
            False,
            {HUMIDITY: "57.25", AUTOMATIC_BYPASS: STATE_ON},
            id="connection-restored",
        ),
    ],
)
async def test_overlapping_polls_wait_for_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_danfoss_client: MagicMock,
    connected_before: bool,
    fetch_fails: bool,
    expected: dict[str, str],
) -> None:
    """Test entities polled during a fetch get the outcome of that fetch."""
    read_values = mock_danfoss_client.command.side_effect
    await setup_integration(hass, mock_config_entry)
    if not connected_before:
        mock_danfoss_client.command.side_effect = OSError("No route to host")
    await _poll(hass, freezer)
    for entity_id in expected:
        unavailable = hass.states.get(entity_id).state == STATE_UNAVAILABLE
        assert unavailable is not connected_before

    fetch_started = threading.Event()
    release_fetch = threading.Event()

    def slow_command(command: ReadCommand) -> float | bool:
        fetch_started.set()
        assert release_fetch.wait(5)
        if fetch_fails:
            raise OSError("timed out")
        return read_values(command)

    mock_danfoss_client.command.side_effect = slow_command
    fetches_before = _fetch_count(mock_danfoss_client)
    freezer.tick(timedelta(seconds=61))

    # Poll a sensor, and while its fetch runs, poll a switch.
    first = hass.async_create_task(async_update_entity(hass, HUMIDITY))
    try:
        assert await hass.async_add_executor_job(fetch_started.wait, 5)
        second = hass.async_create_task(async_update_entity(hass, AUTOMATIC_BYPASS))
        await hass.async_add_executor_job(time.sleep, 0.2)
        waited = not second.done()
    finally:
        release_fetch.set()
    await first
    await second

    assert waited, "the switch poll did not wait for the running fetch"
    assert {entity_id: hass.states.get(entity_id).state for entity_id in expected} == (
        expected
    )
    # Both polls shared one fetch.
    assert _fetch_count(mock_danfoss_client) == fetches_before + 1


@pytest.mark.usefixtures("mock_danfoss_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(HUMIDITY).state == "57.25"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_danfoss_client: MagicMock,
) -> None:
    """Test setup is retried when the CCM module cannot be reached."""
    mock_danfoss_client.command.side_effect = OSError("No route to host")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_danfoss_client")
async def test_import_from_yaml(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the YAML configuration is imported and a deprecation issue is raised."""
    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_HOST: "192.0.2.1"}
    assert entries[0].state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_danfoss_client")
async def test_import_from_yaml_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an already imported YAML configuration only raises the deprecation issue."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (OSError("No route to host"), "cannot_connect"),
        (ValueError("Unexpected"), "unknown"),
    ],
)
async def test_import_from_yaml_fails(
    hass: HomeAssistant,
    mock_danfoss_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test a failed YAML import raises an import issue instead of the deprecation issue."""
    mock_danfoss_client.command.side_effect = side_effect

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
