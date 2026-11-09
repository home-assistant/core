"""The tests for the Proximity component."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.proximity.const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    __version__ as HA_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify


async def async_setup_single_entry(
    hass: HomeAssistant,
    zone: str,
    tracked_entites: list[str],
    ignored_zones: list[str],
    tolerance: int,
) -> MockConfigEntry:
    """Set up the proximity component with a single entry."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={
            CONF_ZONE: zone,
            CONF_TRACKED_ENTITIES: tracked_entites,
            CONF_IGNORED_ZONES: ignored_zones,
            CONF_TOLERANCE: tolerance,
        },
    )
    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()
    return mock_config


@pytest.mark.parametrize(
    "config",
    [
        {
            CONF_IGNORED_ZONES: ["zone.work"],
            CONF_TRACKED_ENTITIES: ["device_tracker.test1", "device_tracker.test2"],
            CONF_TOLERANCE: 1,
            CONF_ZONE: "zone.home",
        },
        {
            CONF_IGNORED_ZONES: [],
            CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            CONF_TOLERANCE: 1,
            CONF_ZONE: "zone.work",
        },
    ],
)
async def test_proximities(hass: HomeAssistant, config: dict) -> None:
    """Test a list of proximities."""
    title = hass.states.get(config[CONF_ZONE]).name
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data=config,
    )
    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

    zone_name = slugify(title)

    # sensor entities
    state = hass.states.get(f"sensor.{zone_name}_nearest_device")
    assert state.state == STATE_UNKNOWN

    for device in config[CONF_TRACKED_ENTITIES]:
        entity_base_name = f"sensor.{zone_name}_{slugify(device.split('.')[-1])}"
        state = hass.states.get(f"{entity_base_name}_distance")
        assert state.state == STATE_UNAVAILABLE
        state = hass.states.get(f"{entity_base_name}_direction_of_travel")
        assert state.state == STATE_UNAVAILABLE


async def test_device_tracker_test1_in_zone(hass: HomeAssistant) -> None:
    """Test for tracker in zone."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {"friendly_name": "test1", "latitude": 2.1, "longitude": 1.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "0"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "arrived"


async def test_device_tracker_test1_away(hass: HomeAssistant) -> None:
    """Test for tracker state away."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )

    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker state away further."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625254"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "away_from"


async def test_device_tracker_test1_awaycloser(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker state away closer."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625254"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "towards"


async def test_all_device_trackers_in_ignored_zone(hass: HomeAssistant) -> None:
    """Test for tracker in ignored zone."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set("device_tracker.test1", "work", {"friendly_name": "test1"})
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_no_coordinates(hass: HomeAssistant) -> None:
    """Test for tracker with no coordinates."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther_a_bit(hass: HomeAssistant) -> None:
    """Test for tracker states."""
    await async_setup_single_entry(
        hass, "zone.home", ["device_tracker.test1"], ["zone.work"], 1000
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1000001, "longitude": 10.1000001},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1000002, "longitude": 10.1000002},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "stationary"


async def test_device_trackers_in_zone(hass: HomeAssistant) -> None:
    """Test for trackers in zone."""
    await async_setup_single_entry(
        hass,
        "zone.home",
        ["device_tracker.test1", "device_tracker.test2"],
        ["zone.work"],
        1,
    )

    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {"friendly_name": "test1", "latitude": 2.1, "longitude": 1.1},
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "device_tracker.test2",
        "home",
        {"friendly_name": "test2", "latitude": 2.1, "longitude": 1.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1, test2"

    for device in ("test1", "test2"):
        entity_base_name = f"sensor.home_{device}"
        state = hass.states.get(f"{entity_base_name}_distance")
        assert state.state == "0"
        state = hass.states.get(f"{entity_base_name}_direction_of_travel")
        assert state.state == "arrived"


@pytest.mark.parametrize(
    "tracker_attributes",
    [
        pytest.param({"in_zones": ["zone.work_office"]}, id="in_zones_attribute"),
        pytest.param({"in_zones": []}, id="empty_in_zones_fallback"),
        pytest.param({}, id="friendly_name_fallback"),
    ],
)
async def test_device_tracker_in_non_home_zone(
    hass: HomeAssistant,
    tracker_attributes: dict[str, Any],
) -> None:
    """Test that a tracker in a non-home zone reports arrived.

    Regression test for zones whose friendly name (which the tracker reports as
    its state) differs from the zone entity id slug, e.g. names with spaces or
    mixed case. The tracker is placed far from the zone centre so that only the
    zone-membership check, not the distance calculation, can yield "arrived".
    """
    hass.states.async_set(
        "zone.work_office",
        "zoning",
        {
            "friendly_name": "Work Office",
            "latitude": 2.3,
            "longitude": 1.3,
            "radius": 10,
        },
    )

    await async_setup_single_entry(
        hass, "zone.work_office", ["device_tracker.test1"], [], 1
    )

    hass.states.async_set(
        "device_tracker.test1",
        "Work Office",
        {
            "friendly_name": "test1",
            "latitude": 20.1,
            "longitude": 10.1,
            **tracker_attributes,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "0"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "arrived"


async def test_overlapping_zones_in_zones_reports_arrived(
    hass: HomeAssistant,
) -> None:
    """Test overlapping proximity zones both report arrived via in_zones.

    Regression test for trackers that report membership in multiple overlapping
    zones via the in_zones attribute while their state only reflects one zone.
    """
    hass.states.async_set(
        "zone.backyard",
        "zoning",
        {
            "friendly_name": "Backyard",
            "latitude": 2.1,
            "longitude": 1.1,
            "radius": 10,
        },
    )

    home_config = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
    )
    backyard_config = MockConfigEntry(
        domain=DOMAIN,
        title="Backyard",
        data={
            CONF_ZONE: "zone.backyard",
            CONF_TRACKED_ENTITIES: ["device_tracker.test1"],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
    )
    home_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(home_config.entry_id)
    backyard_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(backyard_config.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {
            "friendly_name": "test1",
            "latitude": 20.1,
            "longitude": 10.1,
            "in_zones": ["zone.home", "zone.backyard"],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "arrived"
    state = hass.states.get("sensor.backyard_test1_direction_of_travel")
    assert state.state == "arrived"


async def test_legacy_device_tracker_home_with_empty_in_zones(
    hass: HomeAssistant,
) -> None:
    """Test legacy tracker with empty in_zones and home state reports arrived.

    Regression test for legacy device trackers that do not populate in_zones
    but still report their state as home when inside the home zone.
    """
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {
            "friendly_name": "test1",
            "latitude": 20.1,
            "longitude": 10.1,
            "in_zones": [],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "arrived"


async def test_device_tracker_test1_awayfurther_than_test2_first_test1(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker ordering."""
    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )
    await async_setup_single_entry(
        hass,
        "zone.home",
        ["device_tracker.test1", "device_tracker.test2"],
        ["zone.work"],
        1,
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625254"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther_than_test2_first_test2(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker ordering."""
    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )

    await async_setup_single_entry(
        hass,
        "zone.home",
        ["device_tracker.test1", "device_tracker.test2"],
        ["zone.work"],
        1,
    )

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test2"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625254"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625254"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther_test2_in_ignored_zone(
    hass: HomeAssistant,
) -> None:
    """Test for tracker states."""
    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    hass.states.async_set("device_tracker.test2", "work", {"friendly_name": "test2"})

    await async_setup_single_entry(
        hass,
        "zone.home",
        ["device_tracker.test1", "device_tracker.test2"],
        ["zone.work"],
        1,
    )
    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther_test2_first(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker state."""
    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )

    await async_setup_single_entry(
        hass,
        "zone.home",
        ["device_tracker.test1", "device_tracker.test2"],
        ["zone.work"],
        1,
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 10.1, "longitude": 5.1},
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 35.1, "longitude": 15.1},
    )
    await hass.async_block_till_done()

    hass.states.async_set("device_tracker.test1", "work", {"friendly_name": "test1"})
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test2"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_nearest_after_test2_in_ignored_zone(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker states."""
    await hass.async_block_till_done()
    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )
    await hass.async_block_till_done()

    await async_setup_single_entry(
        hass,
        "zone.home",
        ["device_tracker.test1", "device_tracker.test2"],
        ["zone.work"],
        1,
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 10.1, "longitude": 5.1},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test2"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "989146"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        "device_tracker.test2",
        "work",
        {"friendly_name": "test2", "latitude": 12.6, "longitude": 7.6},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "1364557"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "away_from"


async def test_nearest_sensors(hass: HomeAssistant, config_zones) -> None:
    """Test for nearest sensors."""
    await async_setup_single_entry(
        hass, "zone.home", ["device_tracker.test1", "device_tracker.test2"], [], 1
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20, "longitude": 10},
    )
    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 40, "longitude": 20},
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 15, "longitude": 8},
    )
    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 45, "longitude": 22},
    )
    await hass.async_block_till_done()

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"
    state = hass.states.get("sensor.home_nearest_distance")
    assert state.state == "1615580"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == "1615580"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == "5176048"
    state = hass.states.get("sensor.home_test2_direction_of_travel")
    assert state.state == "away_from"

    # move the far tracker
    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 40, "longitude": 20},
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"
    state = hass.states.get("sensor.home_nearest_distance")
    assert state.state == "1615580"
    state = hass.states.get("sensor.home_nearest_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == "1615580"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == "4611394"
    state = hass.states.get("sensor.home_test2_direction_of_travel")
    assert state.state == "towards"

    # move the near tracker
    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20, "longitude": 10},
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"
    state = hass.states.get("sensor.home_nearest_distance")
    assert state.state == "2204112"
    state = hass.states.get("sensor.home_nearest_direction_of_travel")
    assert state.state == "away_from"
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == "2204112"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "away_from"
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == "4611394"
    state = hass.states.get("sensor.home_test2_direction_of_travel")
    assert state.state == "towards"

    # get unknown distance and direction
    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.home_nearest_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.home_nearest_direction_of_travel")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get("sensor.home_test2_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_create_removed_tracked_entity_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test we create an issue for removed tracked entities."""
    t1 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test1"
    )
    t2 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test2"
    )

    hass.states.async_set(t1.entity_id, "not_home")
    hass.states.async_set(t2.entity_id, "not_home")

    assert await async_setup_component(hass, "repairs", {})
    mock_config = await async_setup_single_entry(
        hass, "zone.home", [t1.entity_id, t2.entity_id], [], 1
    )

    sensor_t1 = f"sensor.home_{t1.entity_id.split('.')[-1]}_distance"
    sensor_t2 = f"sensor.home_{t2.entity_id.split('.')[-1]}_distance"

    state = hass.states.get(sensor_t1)
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(sensor_t2)
    assert state.state == STATE_UNKNOWN

    hass.states.async_remove(t2.entity_id)
    entity_registry.async_remove(t2.entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(sensor_t1)
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(sensor_t2)
    assert state.state == STATE_UNAVAILABLE

    issue_id = f"tracked_entity_removed_{mock_config.entry_id}_{t2.entity_id}"
    assert (issue := issue_registry.async_get_issue(DOMAIN, issue_id))
    assert issue.config_entry_id == mock_config.entry_id
    assert issue.is_persistent
    assert issue.translation_placeholders == {
        "entity_id": t2.entity_id,
        "name": "Home",
    }

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "entity_id": t2.entity_id,
        "name": "Home",
    }
    result = await process_repair_fix_flow(client, result["flow_id"])
    assert result["type"] == "create_entry"

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


def _mock_proximity_entry(
    hass: HomeAssistant, title: str, zone: str, tracked_entities: list[str]
) -> MockConfigEntry:
    """Add a proximity config entry to hass without setting it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={
            CONF_ZONE: zone,
            CONF_TRACKED_ENTITIES: tracked_entities,
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_removed_tracked_entity_issue_per_config_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test proximities tracking the same removed entity get separate issues."""
    t1 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test1"
    )
    hass.states.async_set(t1.entity_id, "not_home")
    home_entry = _mock_proximity_entry(hass, "Home", "zone.home", [t1.entity_id])
    work_entry = _mock_proximity_entry(hass, "Work", "zone.work", [t1.entity_id])
    # Sets up both entries
    assert await hass.config_entries.async_setup(home_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_remove(t1.entity_id)
    entity_registry.async_remove(t1.entity_id)
    await hass.async_block_till_done()

    home_issue_id = f"tracked_entity_removed_{home_entry.entry_id}_{t1.entity_id}"
    work_issue_id = f"tracked_entity_removed_{work_entry.entry_id}_{t1.entity_id}"
    assert (home_issue := issue_registry.async_get_issue(DOMAIN, home_issue_id))
    assert home_issue.config_entry_id == home_entry.entry_id
    assert home_issue.translation_placeholders == {
        "entity_id": t1.entity_id,
        "name": "Home",
    }
    assert (work_issue := issue_registry.async_get_issue(DOMAIN, work_issue_id))
    assert work_issue.config_entry_id == work_entry.entry_id
    assert work_issue.translation_placeholders == {
        "entity_id": t1.entity_id,
        "name": "Work",
    }

    assert await hass.config_entries.async_remove(home_entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, home_issue_id)
    assert issue_registry.async_get_issue(DOMAIN, work_issue_id)


async def test_removed_tracked_entity_issue_deleted_when_untracked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the issue is deleted once the removed entity is no longer tracked."""
    t1 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test1"
    )
    t2 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test2"
    )
    hass.states.async_set(t1.entity_id, "not_home")
    hass.states.async_set(t2.entity_id, "not_home")
    home_entry = _mock_proximity_entry(
        hass, "Home", "zone.home", [t1.entity_id, t2.entity_id]
    )
    work_entry = _mock_proximity_entry(hass, "Work", "zone.work", [t2.entity_id])
    assert await hass.config_entries.async_setup(home_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_remove(t2.entity_id)
    entity_registry.async_remove(t2.entity_id)
    await hass.async_block_till_done()

    home_issue_id = f"tracked_entity_removed_{home_entry.entry_id}_{t2.entity_id}"
    work_issue_id = f"tracked_entity_removed_{work_entry.entry_id}_{t2.entity_id}"
    assert issue_registry.async_get_issue(DOMAIN, home_issue_id)
    assert issue_registry.async_get_issue(DOMAIN, work_issue_id)

    result = await hass.config_entries.options.async_init(home_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACKED_ENTITIES: [t1.entity_id],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, home_issue_id)
    assert issue_registry.async_get_issue(DOMAIN, work_issue_id)


@pytest.mark.parametrize(
    ("legacy_dismissed_version", "expected_dismissed_version"),
    [
        pytest.param(None, None, id="not_ignored"),
        pytest.param("2025.1.0", HA_VERSION, id="ignored"),
    ],
)
async def test_migrate_legacy_removed_tracked_entity_issue(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    legacy_dismissed_version: str | None,
    expected_dismissed_version: str | None,
) -> None:
    """Test a legacy removed tracked entity issue is migrated per config entry."""
    tracked_entity_id = "device_tracker.test1"
    untracked_entity_id = "device_tracker.test2"
    home_entry = _mock_proximity_entry(hass, "Home", "zone.home", [tracked_entity_id])
    work_entry = _mock_proximity_entry(hass, "Work", "zone.work", [tracked_entity_id])
    other_entry = _mock_proximity_entry(hass, "Other", "zone.home", [])
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "breaks_in_ha_version": None,
                    "config_entry_id": None,
                    "config_subentry_id": None,
                    "created": "2026-01-01T00:00:00+00:00",
                    "data": None,
                    "dismissed_version": legacy_dismissed_version,
                    "domain": DOMAIN,
                    "is_fixable": True,
                    "is_persistent": True,
                    "issue_domain": None,
                    "issue_id": f"tracked_entity_removed_{entity_id}",
                    "learn_more_url": None,
                    "severity": "warning",
                    "translation_key": "tracked_entity_removed",
                    "translation_placeholders": {
                        "entity_id": entity_id,
                        "name": "Work",
                    },
                }
                for entity_id in (tracked_entity_id, untracked_entity_id)
            ]
        },
    }
    await issue_registry.async_load()

    assert await hass.config_entries.async_setup(home_entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        DOMAIN, f"tracked_entity_removed_{tracked_entity_id}"
    )
    assert not issue_registry.async_get_issue(
        DOMAIN, f"tracked_entity_removed_{untracked_entity_id}"
    )
    assert {
        issue_id: (
            issue.config_entry_id,
            issue.is_persistent,
            issue.translation_placeholders,
            issue.dismissed_version,
        )
        for (domain, issue_id), issue in issue_registry.issues.items()
        if domain == DOMAIN
    } == {
        f"tracked_entity_removed_{entry.entry_id}_{tracked_entity_id}": (
            entry.entry_id,
            True,
            {"entity_id": tracked_entity_id, "name": entry.title},
            expected_dismissed_version,
        )
        for entry in (home_entry, work_entry)
    }
    assert other_entry.state is ConfigEntryState.LOADED


async def test_track_renamed_tracked_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that when tracked entity is renamed."""
    t1 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test1"
    )

    hass.states.async_set(t1.entity_id, "not_home")

    mock_config = await async_setup_single_entry(
        hass, "zone.home", [t1.entity_id], ["zone.work"], 1
    )

    sensor_t1 = f"sensor.home_{t1.entity_id.split('.')[-1]}_distance"

    entity = entity_registry.async_get(sensor_t1)
    assert entity
    assert entity.unique_id == f"{mock_config.entry_id}_{t1.id}_dist_to_zone"

    entity_registry.async_update_entity(
        t1.entity_id, new_entity_id=f"{t1.entity_id}_renamed"
    )
    await hass.async_block_till_done()

    entity = entity_registry.async_get(sensor_t1)
    assert entity
    assert entity.unique_id == f"{mock_config.entry_id}_{t1.id}_dist_to_zone"

    entry = hass.config_entries.async_get_entry(mock_config.entry_id)
    assert entry
    assert entry.data[CONF_TRACKED_ENTITIES] == [f"{t1.entity_id}_renamed"]


async def test_sensor_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that when tracked entity is renamed."""
    t1 = entity_registry.async_get_or_create(
        "device_tracker", "device_tracker", "test1", original_name="Test tracker 1"
    )
    hass.states.async_set(t1.entity_id, "not_home")

    hass.states.async_set("device_tracker.test2", "not_home")

    mock_config = await async_setup_single_entry(
        hass, "zone.home", [t1.entity_id, "device_tracker.test2"], ["zone.work"], 1
    )

    sensor_t1 = "sensor.home_test_tracker_1_distance"
    entity = entity_registry.async_get(sensor_t1)
    assert entity
    assert entity.unique_id == f"{mock_config.entry_id}_{t1.id}_dist_to_zone"
    state = hass.states.get(sensor_t1)
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Home Test tracker 1 distance"

    entity = entity_registry.async_get("sensor.home_test2_distance")
    assert entity
    assert (
        entity.unique_id == f"{mock_config.entry_id}_device_tracker.test2_dist_to_zone"
    )


async def test_tracked_zone_is_removed(hass: HomeAssistant) -> None:
    """Test that tracked zone is removed."""
    await async_setup_single_entry(hass, "zone.home", ["device_tracker.test1"], [], 1)

    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {"friendly_name": "test1", "latitude": 2.1, "longitude": 1.1},
    )
    await hass.async_block_till_done()

    # check sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "0"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "arrived"

    # remove tracked zone and move tracked entity
    assert hass.states.async_remove("zone.home")
    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {"friendly_name": "test1", "latitude": 2.2, "longitude": 1.2},
    )
    await hass.async_block_till_done()

    # check sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNAVAILABLE


async def test_tracked_zone_radius_is_changed(hass: HomeAssistant) -> None:
    """Test that radius of the tracked zone is changed."""
    entry = await async_setup_single_entry(
        hass, "zone.home", ["device_tracker.test1"], [], 1
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.10000001, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # check sensor entities before radius change
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    # change radius of tracked zone
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "Home", "latitude": 2.1, "longitude": 1.1, "radius": 110},
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    radius = hass.states.get("zone.home").attributes["radius"]
    assert radius == 110

    # check sensor entities after radius change
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218642"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_tracked_zone_location_is_changed(hass: HomeAssistant) -> None:
    """Test that gps location of the tracked zone is changed."""
    entry = await async_setup_single_entry(
        hass, "zone.home", ["device_tracker.test1"], [], 1
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # check sensor entities before location change
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218742"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    # change location of tracked zone
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "Home", "latitude": 10, "longitude": 5, "radius": 10},
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    latitude = hass.states.get("zone.home").attributes["latitude"]
    assert latitude == 10
    longitude = hass.states.get("zone.home").attributes["longitude"]
    assert longitude == 5

    # check sensor entities after location change
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1"

    entity_base_name = "sensor.home_test1"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "1244478"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN
