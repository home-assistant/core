"""The tests for the Proximity component."""

import pytest

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.proximity.const import (
    CONF_IGNORED_ZONES,
    CONF_TOLERANCE,
    CONF_TRACKED_ENTITIES,
    DOMAIN,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    CONF_ZONE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("friendly_name", "config"),
    [
        (
            "home",
            {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            },
        ),
        (
            "work",
            {
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
                "zone": "work",
            },
        ),
    ],
)
async def test_proximities(
    hass: HomeAssistant, friendly_name: str, config: dict
) -> None:
    """Test a list of proximities."""
    assert await async_setup_component(
        hass, DOMAIN, {"proximity": {friendly_name: config}}
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get(f"proximity.{friendly_name}")
    assert state.state == "not set"
    assert state.attributes.get("nearest") == "not set"
    assert state.attributes.get("dir_of_travel") == "not set"
    hass.states.async_set(f"proximity.{friendly_name}", "0")
    await hass.async_block_till_done()
    state = hass.states.get(f"proximity.{friendly_name}")
    assert state.state == "0"

    # sensor entities
    state = hass.states.get(f"sensor.{friendly_name}_nearest_device")
    assert state.state == STATE_UNKNOWN

    for device in config["devices"]:
        entity_base_name = f"sensor.{friendly_name}_{slugify(device.split('.')[-1])}"
        state = hass.states.get(f"{entity_base_name}_distance")
        assert state.state == STATE_UNAVAILABLE
        state = hass.states.get(f"{entity_base_name}_direction_of_travel")
        assert state.state == STATE_UNAVAILABLE


async def test_legacy_setup(hass: HomeAssistant) -> None:
    """Test legacy setup only on imported entries."""
    config = {
        "proximity": {
            "home": {
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            },
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.states.get("proximity.home")

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="work",
        data={
            CONF_ZONE: "zone.work",
            CONF_TRACKED_ENTITIES: ["device_tracker.test2"],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
        unique_id=f"{DOMAIN}_work",
    )
    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

    assert not hass.states.get("proximity.work")


async def test_device_tracker_test1_in_zone(hass: HomeAssistant) -> None:
    """Test for tracker in zone."""
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(
        "device_tracker.test1",
        "home",
        {"friendly_name": "test1", "latitude": 2.1, "longitude": 1.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.state == "0"
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "arrived"

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
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )

    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    await hass.async_block_till_done()

    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "away_from"

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
    await hass.async_block_till_done()

    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "towards"

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
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set("device_tracker.test1", "work", {"friendly_name": "test1"})
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.state == "not set"
    assert state.attributes.get("nearest") == "not set"
    assert state.attributes.get("dir_of_travel") == "not set"

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
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "not set"
    assert state.attributes.get("dir_of_travel") == "not set"

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
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "proximity": {
                "home": {
                    "ignored_zones": ["work"],
                    "devices": ["device_tracker.test1"],
                    "tolerance": 1000,
                    "zone": "home",
                }
            }
        },
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1000001, "longitude": 10.1000001},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "stationary"

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
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.state == "0"
    assert (state.attributes.get("nearest") == "test1, test2") or (
        state.attributes.get("nearest") == "test2, test1"
    )
    assert state.attributes.get("dir_of_travel") == "arrived"

    # sensor entities
    state = hass.states.get("sensor.home_nearest_device")
    assert state.state == "test1, test2"

    for device in ["test1", "test2"]:
        entity_base_name = f"sensor.home_{device}"
        state = hass.states.get(f"{entity_base_name}_distance")
        assert state.state == "0"
        state = hass.states.get(f"{entity_base_name}_direction_of_travel")
        assert state.state == "arrived"


async def test_device_tracker_test1_awayfurther_than_test2_first_test1(
    hass: HomeAssistant, config_zones
) -> None:
    """Test for tracker ordering."""
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "proximity": {
                "home": {
                    "ignored_zones": ["work"],
                    "devices": ["device_tracker.test1", "device_tracker.test2"],
                    "tolerance": "1",
                    "zone": "home",
                }
            }
        },
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "proximity": {
                "home": {
                    "ignored_zones": ["work"],
                    "devices": ["device_tracker.test1", "device_tracker.test2"],
                    "zone": "home",
                }
            }
        },
    )

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test2"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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
    await hass.async_block_till_done()
    hass.states.async_set("device_tracker.test2", "work", {"friendly_name": "test2"})
    await hass.async_block_till_done()
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "proximity": {
                "home": {
                    "ignored_zones": ["work"],
                    "devices": ["device_tracker.test1", "device_tracker.test2"],
                    "zone": "home",
                }
            }
        },
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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
    await hass.async_block_till_done()

    hass.states.async_set(
        "device_tracker.test1", "not_home", {"friendly_name": "test1"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        "device_tracker.test2", "not_home", {"friendly_name": "test2"}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "proximity": {
                "home": {
                    "ignored_zones": ["work"],
                    "devices": ["device_tracker.test1", "device_tracker.test2"],
                    "zone": "home",
                }
            }
        },
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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test2"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "proximity": {
                "home": {
                    "ignored_zones": ["work"],
                    "devices": ["device_tracker.test1", "device_tracker.test2"],
                    "zone": "home",
                }
            }
        },
    )

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test2"
    assert state.attributes.get("dir_of_travel") == "unknown"

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

    # proximity entity
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

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
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: ["device_tracker.test1", "device_tracker.test2"],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
        unique_id=f"{DOMAIN}_home",
    )

    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

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


async def test_create_deprecated_proximity_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue for deprecated proximity entities used in automations and scripts."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": "proximity.home"},
                "action": {
                    "service": "automation.turn_on",
                    "target": {"entity_id": "automation.test"},
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": [
                        {
                            "condition": "state",
                            "entity_id": "proximity.home",
                            "state": "home",
                        },
                    ],
                }
            }
        },
    )
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            },
            "work": {"tolerance": "1", "zone": "work"},
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    automation_entities = automations_with_entity(hass, "proximity.home")
    assert len(automation_entities) == 1
    assert automation_entities[0] == "automation.test"

    script_entites = scripts_with_entity(hass, "proximity.home")

    assert len(script_entites) == 1
    assert script_entites[0] == "script.test"
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_proximity_entity_home")

    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_proximity_entity_work"
    )


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

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: [t1.entity_id, t2.entity_id],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
        unique_id=f"{DOMAIN}_home",
    )

    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

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

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: [t1.entity_id],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
        unique_id=f"{DOMAIN}_home",
    )

    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

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

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        title="home",
        data={
            CONF_ZONE: "zone.home",
            CONF_TRACKED_ENTITIES: [t1.entity_id, "device_tracker.test2"],
            CONF_IGNORED_ZONES: [],
            CONF_TOLERANCE: 1,
        },
        unique_id=f"{DOMAIN}_home",
    )

    mock_config.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config.entry_id)
    await hass.async_block_till_done()

    sensor_t1 = "sensor.home_test_tracker_1_distance"
    entity = entity_registry.async_get(sensor_t1)
    assert entity
    assert entity.unique_id == f"{mock_config.entry_id}_{t1.id}_dist_to_zone"
    state = hass.states.get(sensor_t1)
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "home Test tracker 1 Distance"

    entity = entity_registry.async_get("sensor.home_test2_distance")
    assert entity
    assert (
        entity.unique_id == f"{mock_config.entry_id}_device_tracker.test2_dist_to_zone"
    )
