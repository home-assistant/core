"""The tests for the Proximity component."""

import pytest

from homeassistant.components.proximity.const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.util import slugify

from tests.common import MockConfigEntry


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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
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
    assert state.state == "4625264"
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
    assert state.state == "4625264"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625264"
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
    assert state.state == "4625264"
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
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625264"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
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
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "989156"
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
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = "sensor.home_test2"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "1364567"
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
    assert state.state == "1615590"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == "1615590"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == "5176058"
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
    assert state.state == "1615590"
    state = hass.states.get("sensor.home_nearest_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == "1615590"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "towards"
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == "4611404"
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
    assert state.state == "2204122"
    state = hass.states.get("sensor.home_nearest_direction_of_travel")
    assert state.state == "away_from"
    state = hass.states.get("sensor.home_test1_distance")
    assert state.state == "2204122"
    state = hass.states.get("sensor.home_test1_direction_of_travel")
    assert state.state == "away_from"
    state = hass.states.get("sensor.home_test2_distance")
    assert state.state == "4611404"
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

    await async_setup_single_entry(
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

    assert issue_registry.async_get_issue(
        DOMAIN, f"tracked_entity_removed_{t2.entity_id}"
    )


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
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Home Test tracker 1 Distance"

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
