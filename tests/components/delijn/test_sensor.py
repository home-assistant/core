"""Test the De Lijn sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pydelijn import (
    DeLijnAuthError,
    DeLijnConnectionError,
    DeLijnError,
    DeLijnNotFoundError,
    DeLijnResponseError,
    Line,
    Passage,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.delijn.const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    DOMAIN,
    SCAN_INTERVAL,
)
from homeassistant.components.delijn.sensor import CONF_NEXT_DEPARTURE
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import STOP_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

API_KEY = "test-api-key"


async def test_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the De Lijn sensor entity state and attributes."""
    freezer.move_to("2026-08-06T12:00:00+00:00")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_no_passages(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor when there are no upcoming passages."""
    mock_delijn_client.get_passages.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.unique_id}_next_departure"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["line_number_public"] is None
    assert state.attributes["next_passages"] == []


async def test_sensor_passage_without_due_time(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_line: Line,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a passage without a known due time reports due_in_min as None."""
    mock_delijn_client.get_passages.return_value = [
        Passage(line=mock_line, due_at_schedule=None, due_at_realtime=None),
    ]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.unique_id}_next_departure"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["next_passages"][0]["due_in_min"] is None


async def test_sensor_becomes_unavailable_on_update_failure(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor becomes unavailable when a coordinator update fails."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{load_integration.unique_id}_next_departure"
    )
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    mock_delijn_client.get_passages.side_effect = DeLijnConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_yaml_import(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing the legacy YAML sensor platform configuration."""
    config = {
        "sensor": {
            "platform": DOMAIN,
            CONF_API_KEY: API_KEY,
            CONF_NEXT_DEPARTURE: [
                {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
            ],
        }
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_STOP_NUMBER] == STOP_NUMBER
    assert entries[0].options == {CONF_NUMBER_OF_DEPARTURES: 3}

    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn")
    assert not issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{STOP_NUMBER}_invalid_stop"
    )


async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed YAML import creates a per-stop repair issue."""
    mock_delijn_client.get_stop.side_effect = DeLijnNotFoundError
    unknown_stop = "999999"

    config = {
        "sensor": {
            "platform": DOMAIN,
            CONF_API_KEY: API_KEY,
            CONF_NEXT_DEPARTURE: [
                {CONF_STOP_ID: unknown_stop, CONF_NUMBER_OF_DEPARTURES: 3},
            ],
        }
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{unknown_stop}_invalid_stop"
    )
    assert issue
    assert issue.translation_key == "deprecated_yaml_import_issue_invalid_stop"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn")


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        (DeLijnNotFoundError, "invalid_stop"),
        (DeLijnAuthError, "invalid_auth"),
        (DeLijnConnectionError, "cannot_connect"),
        (DeLijnResponseError, "unknown"),
    ],
)
async def test_yaml_import_failure_translation_key_per_reason(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    side_effect: type[DeLijnError],
    expected_reason: str,
) -> None:
    """Test each import failure reason maps to its own translation key."""
    mock_delijn_client.get_stop.side_effect = side_effect
    unknown_stop = "999999"

    config = {
        "sensor": {
            "platform": DOMAIN,
            CONF_API_KEY: API_KEY,
            CONF_NEXT_DEPARTURE: [
                {CONF_STOP_ID: unknown_stop, CONF_NUMBER_OF_DEPARTURES: 3},
            ],
        }
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{unknown_stop}_{expected_reason}"
    )
    assert issue
    assert issue.translation_key == f"deprecated_yaml_import_issue_{expected_reason}"
