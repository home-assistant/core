"""The tests for the Proximity component."""
from homeassistant.components.proximity import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_proximities(hass: HomeAssistant) -> None:
    """Test a list of proximities."""
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            },
            "work": {"devices": ["device_tracker.test1"], "tolerance": "1"},
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)

    proximities = ["home", "work"]

    for prox in proximities:
        state = hass.states.get(f"proximity.{prox}")
        assert state.state == "not set"
        assert state.attributes.get("nearest") == "not set"
        assert state.attributes.get("dir_of_travel") == "not set"

        hass.states.async_set(f"proximity.{prox}", "0")
        await hass.async_block_till_done()
        state = hass.states.get(f"proximity.{prox}")
        assert state.state == "0"


async def test_proximities_setup(hass: HomeAssistant) -> None:
    """Test a list of proximities with missing devices."""
    config = {
        "proximity": {
            "home": {
                "ignored_zones": ["work"],
                "devices": ["device_tracker.test1", "device_tracker.test2"],
                "tolerance": "1",
            },
            "work": {"tolerance": "1"},
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)


async def test_proximity(hass: HomeAssistant) -> None:
    """Test the proximity."""
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

    state = hass.states.get("proximity.home")
    assert state.state == "not set"
    assert state.attributes.get("nearest") == "not set"
    assert state.attributes.get("dir_of_travel") == "not set"

    hass.states.async_set("proximity.home", "0")
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.state == "0"


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
    state = hass.states.get("proximity.home")
    assert state.state == "0"
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "arrived"


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
    state = hass.states.get("proximity.home")
    assert state.state == "0"
    assert (state.attributes.get("nearest") == "test1, test2") or (
        state.attributes.get("nearest") == "test2, test1"
    )
    assert state.attributes.get("dir_of_travel") == "arrived"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "away_from"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "towards"


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
    state = hass.states.get("proximity.home")
    assert state.state == "not set"
    assert state.attributes.get("nearest") == "not set"
    assert state.attributes.get("dir_of_travel") == "not set"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "not set"
    assert state.attributes.get("dir_of_travel") == "not set"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 40.1, "longitude": 20.1},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test2"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1, "longitude": 10.1},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"


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

    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test2"
    assert state.attributes.get("dir_of_travel") == "unknown"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test1",
        "not_home",
        {"friendly_name": "test1", "latitude": 20.1000002, "longitude": 10.1000002},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "stationary"


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
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test2",
        "not_home",
        {"friendly_name": "test2", "latitude": 10.1, "longitude": 5.1},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test2"
    assert state.attributes.get("dir_of_travel") == "unknown"

    hass.states.async_set(
        "device_tracker.test2",
        "work",
        {"friendly_name": "test2", "latitude": 12.6, "longitude": 7.6},
    )
    await hass.async_block_till_done()
    state = hass.states.get("proximity.home")
    assert state.attributes.get("nearest") == "test1"
    assert state.attributes.get("dir_of_travel") == "unknown"


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
