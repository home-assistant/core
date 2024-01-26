"""The tests for the Proximity component."""

import pytest

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.proximity import DOMAIN
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify


@pytest.mark.parametrize(("friendly_name"), ["home", "home_test2", "work"])
async def test_proximities(hass: HomeAssistant, friendly_name: str) -> None:
    """Test a list of proximities."""
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            },
            "home_test2": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            },
            "work": {
                "devices": ["device_tracker.test1"],
                "tolerance": "1",
                "zone": "work",
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
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
    state = hass.states.get(f"sensor.{friendly_name}_nearest")
    assert state.state == STATE_UNKNOWN

    for device in config["proximity"][friendly_name]["devices"]:
        entity_base_name = f"sensor.{friendly_name}_{slugify(device)}"
        state = hass.states.get(f"{entity_base_name}_distance")
        assert state.state == STATE_UNKNOWN
        state = hass.states.get(f"{entity_base_name}_direction_of_travel")
        assert state.state == STATE_UNKNOWN


async def test_proximities_setup(hass: HomeAssistant) -> None:
    """Test a list of proximities with missing devices."""
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "11912010"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther(hass: HomeAssistant) -> None:
    """Test for tracker state away further."""

    config_zones(hass)
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625264"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "away_from"


async def test_device_tracker_test1_awaycloser(hass: HomeAssistant) -> None:
    """Test for tracker state away closer."""
    config_zones(hass)
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "11912010"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "11912010"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1, test2"

    for device in ["device_tracker.test1", "device_tracker.test2"]:
        entity_base_name = f"sensor.home_{slugify(device)}"
        state = hass.states.get(f"{entity_base_name}_distance")
        assert state.state == "0"
        state = hass.states.get(f"{entity_base_name}_direction_of_travel")
        assert state.state == "arrived"


async def test_device_tracker_test1_awayfurther_than_test2_first_test1(
    hass: HomeAssistant,
) -> None:
    """Test for tracker ordering."""
    config_zones(hass)
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "4625264"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther_than_test2_first_test2(
    hass: HomeAssistant,
) -> None:
    """Test for tracker ordering."""
    config_zones(hass)
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test2"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "11912010"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_awayfurther_test2_first(
    hass: HomeAssistant,
) -> None:
    """Test for tracker state."""
    config_zones(hass)
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test2"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == STATE_UNKNOWN
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_test1_nearest_after_test2_in_ignored_zone(
    hass: HomeAssistant,
) -> None:
    """Test for tracker states."""
    config_zones(hass)
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test2"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
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
    state = hass.states.get("sensor.home_nearest")
    assert state.state == "test1"

    entity_base_name = f"sensor.home_{slugify('device_tracker.test1')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "2218752"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == STATE_UNKNOWN

    entity_base_name = f"sensor.home_{slugify('device_tracker.test2')}"
    state = hass.states.get(f"{entity_base_name}_distance")
    assert state.state == "1364567"
    state = hass.states.get(f"{entity_base_name}_direction_of_travel")
    assert state.state == "away_from"


async def test_create_issue(
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


def config_zones(hass):
    """Set up zones for test."""
    hass.config.components.add("zone")
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )
    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 2.3, "longitude": 1.3, "radius": 10},
    )
