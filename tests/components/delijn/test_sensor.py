"""Test the De Lijn sensor platform."""

import asyncio
from datetime import UTC, datetime
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pydelijn import (
    DeLijnAuthError,
    DeLijnConnectionError,
    DeLijnError,
    DeLijnNotFoundError,
    DeLijnResponseError,
    Line,
    Passage,
    Stop,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.delijn.const import (
    CONF_NUMBER_OF_DEPARTURES,
    CONF_STOP_ID,
    CONF_STOP_NUMBER,
    DOMAIN,
    SCAN_INTERVAL,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.components.delijn.sensor import (
    CONF_NEXT_DEPARTURE,
    _async_add_subentries_to_entry,
    async_setup_platform,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .conftest import API_KEY, STOP_NUMBER

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the De Lijn sensor entity state and attributes."""
    freezer.move_to("2026-08-06T12:00:00+00:00")
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_subentry.entry_id
    )


async def test_sensor_device_info(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device card exposes a delijn.be link and the stop number."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, STOP_NUMBER)})
    assert device is not None
    assert device.configuration_url == f"https://www.delijn.be/nl/haltes/{STOP_NUMBER}/"
    assert device.model == "Stop"
    assert device.model_id == STOP_NUMBER


async def test_sensor_no_passages(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor when there are no upcoming passages."""
    mock_delijn_client.get_passages.return_value = []
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{STOP_NUMBER}_next_departure"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["line_number_public"] is None
    assert state.attributes["next_passages"] == []


async def test_sensor_passage_without_due_time(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_line: Line,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a passage without a known due time reports due_in_min as None."""
    mock_delijn_client.get_passages.return_value = [
        Passage(line=mock_line, due_at_schedule=None, due_at_realtime=None),
    ]
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{STOP_NUMBER}_next_departure"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["next_passages"][0]["due_in_min"] is None


async def test_sensor_due_in_min_truncates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_line: Line,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test due_in_min truncates towards zero, matching pydelijn 1.x.

    A passage due in 1 minute 40 seconds must report 1, not 2 as rounding
    to the nearest minute would.
    """
    freezer.move_to("2026-08-06T12:00:00+00:00")
    mock_delijn_client.get_passages.return_value = [
        Passage(
            line=mock_line, due_at_schedule=datetime(2026, 8, 6, 12, 1, 40, tzinfo=UTC)
        ),
    ]
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{STOP_NUMBER}_next_departure"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["next_passages"][0]["due_in_min"] == 1


async def test_sensor_passage_without_colours(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    mock_line: Line,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a line without known colours reports the colour attributes as None."""
    line_without_colours = Line(
        entity_number=mock_line.entity_number, number=mock_line.number
    )
    mock_delijn_client.get_passages.return_value = [
        Passage(line=line_without_colours),
    ]
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{STOP_NUMBER}_next_departure"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    passage = state.attributes["next_passages"][0]
    assert passage["line_number_colourFront"] is None
    assert passage["line_number_colourFrontHex"] is None
    assert passage["line_number_colourBack"] is None
    assert passage["line_number_colourBackHex"] is None
    assert passage["line_number_colourFrontBorder"] is None
    assert passage["line_number_colourFrontBorderHex"] is None
    assert passage["line_number_colourBackBorder"] is None
    assert passage["line_number_colourBackBorderHex"] is None


async def test_sensor_becomes_unavailable_on_update_failure(
    hass: HomeAssistant,
    load_integration: MockConfigEntry,
    mock_delijn_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor becomes unavailable when a coordinator update fails."""
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{STOP_NUMBER}_next_departure"
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
    assert entries[0].data == {CONF_API_KEY: API_KEY}
    assert len(entries[0].subentries) == 1
    subentry = next(iter(entries[0].subentries.values()))
    assert subentry.unique_id == STOP_NUMBER
    assert subentry.data == {
        CONF_STOP_NUMBER: STOP_NUMBER,
        CONF_NUMBER_OF_DEPARTURES: 3,
    }

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{STOP_NUMBER}"
    )


async def test_yaml_import_multiple_stops_creates_all_sensors(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test importing several YAML stops creates a sensor for every stop.

    Regression test: adding each subentry used to fire an overlapping
    entry reload that could settle on only the first stop's sensor.
    """
    stop_numbers = ["200112", "200113", "200114"]
    mock_delijn_client.get_stop.side_effect = [
        Stop(
            entity_number="2",
            number=number,
            name=f"Stop {number}",
            municipality="Gent",
        )
        for number in stop_numbers
    ]

    config = {
        "sensor": {
            "platform": DOMAIN,
            CONF_API_KEY: API_KEY,
            CONF_NEXT_DEPARTURE: [
                {CONF_STOP_ID: number, CONF_NUMBER_OF_DEPARTURES: 3}
                for number in stop_numbers
            ],
        }
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert len(entries[0].subentries) == 3

    # One get_passages call per stop coordinator proves the entry was set
    # up exactly once with its full final state, not once per stop.
    assert mock_delijn_client.get_passages.call_count == len(stop_numbers)

    for number in stop_numbers:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{number}_next_departure"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id) is not None


async def test_yaml_import_multiple_stops_added_to_existing_entry_once(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test importing several stops into an already-loaded entry reloads once.

    Adding each subentry to a loaded entry used to queue its own listener
    reload; asserting one get_passages call per stop proves the entry is
    set up exactly once with the complete set of stops, not once per stop.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_delijn_client.get_passages.reset_mock()

    stop_numbers = ["200112", "200113", "200114"]
    mock_delijn_client.get_stop.side_effect = [
        Stop(
            entity_number="2",
            number=number,
            name=f"Stop {number}",
            municipality="Gent",
        )
        for number in stop_numbers
    ]

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: number, CONF_NUMBER_OF_DEPARTURES: 3}
            for number in stop_numbers
        ],
    }
    await async_setup_platform(hass, platform_config, MagicMock())
    await hass.async_block_till_done()

    assert len(mock_config_entry.subentries) == 3
    assert mock_delijn_client.get_passages.call_count == len(stop_numbers)

    for number in stop_numbers:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{number}_next_departure"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id) is not None


async def test_yaml_import_concurrent_blocks_same_key_no_duplicate_error(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test two concurrent YAML platform blocks importing the same account.

    Overlapping stops previously raced past validation together: both
    passed, and the loser's subentry add raised AbortFlow, aborting that
    block's import before its repair-issue bookkeeping ran. The import
    lock now serializes the two blocks so this can no longer race.
    """
    overlapping_stop = STOP_NUMBER
    unique_stop_a = "200113"
    unique_stop_b = "200114"

    async def _get_stop(stop_id: str) -> Stop:
        return Stop(
            entity_number="2",
            number=stop_id,
            name=f"Stop {stop_id}",
            municipality="Gent",
        )

    mock_delijn_client.get_stop.side_effect = _get_stop

    config_a = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: overlapping_stop, CONF_NUMBER_OF_DEPARTURES: 3},
            {CONF_STOP_ID: unique_stop_a, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    config_b = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: overlapping_stop, CONF_NUMBER_OF_DEPARTURES: 3},
            {CONF_STOP_ID: unique_stop_b, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }

    await asyncio.gather(
        async_setup_platform(hass, config_a, MagicMock()),
        async_setup_platform(hass, config_b, MagicMock()),
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    subentry_numbers = {
        subentry.unique_id for subentry in entries[0].subentries.values()
    }
    assert subentry_numbers == {overlapping_stop, unique_stop_a, unique_stop_b}

    for number in subentry_numbers:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{number}_next_departure"
        )
        assert entity_id is not None
        assert hass.states.get(entity_id) is not None

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )


async def test_add_subentries_to_entry_skips_stop_added_concurrently_elsewhere(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_stop: Stop,
) -> None:
    """Test a stop added to another entry while unloading isn't re-added.

    Unloading the entry awaits; a concurrent subentry flow (e.g. from the
    UI) could add one of the pending stops to a *different* entry in that
    window (sensor unique ids are global). ``async_add_subentry`` raises
    ``AbortFlow`` on a duplicate unique_id, so each stop is re-checked
    against all entries immediately before it's added and skipped if
    another task already added it anywhere.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    other_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "other-api-key"}, title="De Lijn"
    )
    other_entry.add_to_hass(hass)

    real_async_unload = hass.config_entries.async_unload
    raced = False

    async def _unload_and_race(entry_id: str, **kwargs: object) -> bool:
        nonlocal raced
        result = await real_async_unload(entry_id, **kwargs)
        if not raced:
            raced = True
            hass.config_entries.async_add_subentry(
                other_entry,
                ConfigSubentry(
                    data=MappingProxyType(
                        {CONF_STOP_NUMBER: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 5}
                    ),
                    subentry_type=SUBENTRY_TYPE_STOP,
                    title="Racing subentry",
                    unique_id=STOP_NUMBER,
                ),
            )
        return result

    with patch.object(
        hass.config_entries, "async_unload", side_effect=_unload_and_race
    ):
        await _async_add_subentries_to_entry(hass, mock_config_entry, [(mock_stop, 5)])

    assert not mock_config_entry.subentries
    assert len(other_entry.subentries) == 1


async def test_yaml_import_skips_stop_configured_on_another_entry(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML import skips a stop already configured on a different entry.

    Sensor unique ids are scoped to the stop number only; importing the
    same stop into a second account would silently collide, so it is
    treated as already-configured: no API call, no add.
    """
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()
    mock_delijn_client.get_stop.reset_mock()

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: "other-api-key",
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, platform_config, MagicMock())
    await hass.async_block_till_done()

    mock_delijn_client.get_stop.assert_not_called()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert not issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{STOP_NUMBER}"
    )


async def test_yaml_import_new_entry_drops_stop_added_to_another_entry(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the new-entry import path drops a stop configured elsewhere mid-validation.

    Every stop is validated (the only part that awaits) before this brand
    new entry is created with them all as subentries. Validating the
    second stop here also adds the first one to a different entry, standing
    in for a concurrent UI subentry flow racing in during that await; the
    first stop must be dropped at commit time instead of reaching entry
    creation with a unique_id that collides globally.
    """
    raced_stop = STOP_NUMBER
    trigger_stop = "200113"
    other_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "other-api-key"}, title="De Lijn"
    )
    other_entry.add_to_hass(hass)

    async def _get_stop(stop_id: str) -> Stop:
        if stop_id == trigger_stop:
            hass.config_entries.async_add_subentry(
                other_entry,
                ConfigSubentry(
                    data=MappingProxyType(
                        {CONF_STOP_NUMBER: raced_stop, CONF_NUMBER_OF_DEPARTURES: 5}
                    ),
                    subentry_type=SUBENTRY_TYPE_STOP,
                    title=f"Stop {raced_stop}",
                    unique_id=raced_stop,
                ),
            )
        return Stop(
            entity_number="2",
            number=stop_id,
            name=f"Stop {stop_id}",
            municipality="Gent",
        )

    mock_delijn_client.get_stop.side_effect = _get_stop

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: raced_stop, CONF_NUMBER_OF_DEPARTURES: 3},
            {CONF_STOP_ID: trigger_stop, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, platform_config, MagicMock())
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    new_entry = next(entry for entry in entries if entry.data[CONF_API_KEY] == API_KEY)
    assert {subentry.unique_id for subentry in new_entry.subentries.values()} == {
        trigger_stop
    }
    assert not issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{raced_stop}"
    )


async def test_yaml_import_failure_tracked_per_account_for_same_stop(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failure under one API key isn't hidden by success under another.

    The generic deprecated-YAML notice is gated on a failed-import set keyed
    by (api_key, stop_id); a second account's block successfully importing
    the same stop id must only resolve that account's own failure, not
    another account's, so the generic notice must stay withheld. (The
    per-stop repair issue itself stays stop-scoped and may be cleared by
    either account's success — that's expected.)
    """
    shared_stop_id = STOP_NUMBER
    failing_key = "account-a-key"
    succeeding_key = "account-b-key"

    mock_delijn_client.get_stop.side_effect = DeLijnNotFoundError
    failing_config = {
        "platform": DOMAIN,
        CONF_API_KEY: failing_key,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: shared_stop_id, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, failing_config, MagicMock())
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )

    mock_delijn_client.get_stop.side_effect = None
    succeeding_config = {
        "platform": DOMAIN,
        CONF_API_KEY: succeeding_key,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: shared_stop_id, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, succeeding_config, MagicMock())
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_API_KEY: succeeding_key}
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )


async def test_yaml_import_adds_to_existing_entry(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML adds a stop subentry to an existing entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, platform_config, MagicMock())
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_config_entry.subentries) == 1


async def test_yaml_import_race_falls_back_to_lookup(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the entry lookup falls back if it appears between check and creation."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    with patch(
        "homeassistant.components.delijn.sensor._find_entry_by_api_key",
        side_effect=[None, mock_config_entry],
    ):
        await async_setup_platform(hass, platform_config, MagicMock())
        await hass.async_block_till_done()

    assert len(mock_config_entry.subentries) == 1


async def test_yaml_import_duplicate_canonical_number_skipped(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test two differently-spelled YAML stop ids resolving to the same stop.

    The pre-API-call check only catches an exact stop_id match; a second
    check after the lookup catches stops that resolve to the same canonical
    number under a different spelling.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
            {CONF_STOP_ID: f"0{STOP_NUMBER}", CONF_NUMBER_OF_DEPARTURES: 5},
        ],
    }
    await async_setup_platform(hass, platform_config, MagicMock())
    await hass.async_block_till_done()

    assert len(mock_config_entry.subentries) == 1


async def test_yaml_import_duplicate_stop_no_api_call(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    mock_config_entry_with_subentry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a stop already configured on the entry is skipped without an API call."""
    mock_config_entry_with_subentry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_with_subentry.entry_id)
    await hass.async_block_till_done()

    platform_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    mock_delijn_client.get_stop.reset_mock()
    await async_setup_platform(hass, platform_config, MagicMock())
    await hass.async_block_till_done()

    assert len(mock_config_entry_with_subentry.subentries) == 1
    mock_delijn_client.get_stop.assert_not_called()
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )


async def test_yaml_import_failure_creates_issue(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed YAML import creates a stable per-stop repair issue.

    No entry is created since no stop was successfully validated, and the
    generic deprecated-YAML notice must not be shown, since telling the user
    to remove the YAML config would prevent this stop's retry.
    """
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
        DOMAIN, f"deprecated_yaml_import_issue_{unknown_stop}"
    )
    assert issue
    assert issue.translation_key == "deprecated_yaml_import_issue_invalid_stop"
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )


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
        DOMAIN, f"deprecated_yaml_import_issue_{unknown_stop}"
    )
    assert issue
    assert issue.translation_key == f"deprecated_yaml_import_issue_{expected_reason}"


async def test_yaml_import_retry_clears_issue(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a successful re-import clears a previously reported failure issue."""
    issue_id = f"deprecated_yaml_import_issue_{STOP_NUMBER}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml_import_issue_cannot_connect",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "De Lijn",
            "stop_id": STOP_NUMBER,
        },
    )

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

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_yaml_import_partial_failure_no_generic_issue(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the generic deprecated-YAML issue is withheld when a stop fails.

    A previously created generic notice must also be removed.
    """
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml_delijn",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": "De Lijn"},
    )
    unknown_stop = "999999"
    mock_delijn_client.get_stop.side_effect = [
        mock_delijn_client.get_stop.return_value,
        DeLijnNotFoundError,
    ]

    config = {
        "sensor": {
            "platform": DOMAIN,
            CONF_API_KEY: API_KEY,
            CONF_NEXT_DEPARTURE: [
                {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
                {CONF_STOP_ID: unknown_stop, CONF_NUMBER_OF_DEPARTURES: 3},
            ],
        }
    }
    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert len(entries[0].subentries) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{unknown_stop}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )


async def test_yaml_import_failure_in_other_block_suppresses_generic_issue(
    hass: HomeAssistant,
    mock_delijn_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failure in one YAML platform block outlives a later, clean block.

    Failed stop ids are tracked globally across platform blocks, not just
    within a single ``async_setup_platform`` call, so a later block whose
    own stops all import successfully must not resurrect the generic
    deprecated-YAML notice while an earlier block's stop still needs the
    YAML config to retry.
    """
    unknown_stop = "999999"
    mock_delijn_client.get_stop.side_effect = DeLijnNotFoundError

    failing_config = {
        "platform": DOMAIN,
        CONF_API_KEY: API_KEY,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: unknown_stop, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, failing_config, MagicMock())
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )

    mock_delijn_client.get_stop.side_effect = None
    other_api_key = "other-api-key"
    succeeding_config = {
        "platform": DOMAIN,
        CONF_API_KEY: other_api_key,
        CONF_NEXT_DEPARTURE: [
            {CONF_STOP_ID: STOP_NUMBER, CONF_NUMBER_OF_DEPARTURES: 3},
        ],
    }
    await async_setup_platform(hass, succeeding_config, MagicMock())
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_API_KEY: other_api_key}
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{unknown_stop}"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_delijn"
    )
