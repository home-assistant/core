"""The test for the Anomaly sensor platform."""
from datetime import timedelta
from os import path
from unittest.mock import patch

from homeassistant import config as hass_config, setup
from homeassistant.components.anomaly import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_up_and_off(hass: HomeAssistant):
    """Test up anomaly."""

    print("starting test_up_and_off1")
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "11")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    await hass.async_block_till_done()
    print("done")


async def test_down_and_off(hass: HomeAssistant):
    """Test down anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"
    hass.states.async_set("sensor.test_state", "0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_positive_only(hass: HomeAssistant):
    """Test up anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                        "positive_only": True,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    hass.states.async_set("sensor.test_state", "11")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"
    hass.states.async_set("sensor.test_state", "11")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_negative_only(hass: HomeAssistant):
    """Test up anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                        "negative_only": True,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    hass.states.async_set("sensor.test_state", "11")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "0")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "0")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_up_using_amount(hass: HomeAssistant):
    """Test up anomaly using many samples."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "max_samples": 3,
                        "max_trailing_samples": 7,
                        "min_change_amount": 5,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow()

    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"

    for val in [1, 2, 3, 30, 31, 32]:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()
        now += timedelta(seconds=2)

    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"

    # have to change state value, otherwise sample will lost
    for val in [30, 31, 32, 33]:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()
        now += timedelta(seconds=2)

    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_down_using_amount(hass: HomeAssistant):
    """Test down anomaly using many samples."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "max_samples": 3,
                        "max_trailing_samples": 7,
                        "min_change_amount": 5,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow()
    for val in [30, 31, 32, 33, 1, 2, 3]:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()
        now += timedelta(seconds=2)

    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"

    for val in [0, 1, 2, 3]:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()
        now += timedelta(seconds=2)

    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_invert_up_and_on(hass: HomeAssistant):
    """Test up anomly with invert."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "invert": "Yes",
                        "min_change_amount": 3,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    hass.states.async_set("sensor.test_state", "11")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"


async def test_invert_down_and_on(hass: HomeAssistant):
    """Test down anomaly with invert."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "invert": "Yes",
                        "min_change_amount": 3,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "10")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    hass.states.async_set("sensor.test_state", "0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"


async def test_attribute_up(hass: HomeAssistant):
    """Test attribute up anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                        "attribute": "attr",
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "State", {"attr": "1"})
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "State", {"attr": "10"})
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"


async def test_attribute_down(hass: HomeAssistant):
    """Test attribute down anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                        "attribute": "attr",
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "State", {"attr": "10"})
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "State", {"attr": "1"})
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"


async def test_require_both(hass: HomeAssistant):
    """Test attribute down anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 10,
                        "min_change_percent": 99,
                        "require_both": True,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "0")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "6")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.attributes.get("change_amount") == 3
    assert state.attributes.get("change_percent") == 100
    assert state.state == "off"
    hass.states.async_set("sensor.test_state", "1000")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1050")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.attributes.get("change_amount") == 25
    assert state.attributes.get("change_percent") < 2.5
    assert state.state == "off"
    hass.states.async_set("sensor.test_state", "1000")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "1")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"


async def test_max_samples(hass: HomeAssistant):
    """Test that sample count is limited correctly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                        "max_samples": 3,
                        "max_trailing_samples": 6,
                        "sample_duration": 7,
                        "trailing_sample_duration": 15,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    for val in [0, 1, 2, 3, 50, 51, 52]:
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"
    assert state.attributes["sample_count"] == 3
    assert state.attributes["trailing_sample_count"] == 6


async def test_max_samples_time(hass: HomeAssistant):
    """Test that sample count is limited correctly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                        "max_samples": 100,
                        "max_trailing_samples": 100,
                        "sample_duration": 7,
                        "trailing_sample_duration": 15,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    now = dt_util.utcnow() - timedelta(seconds=20)
    for val in [0, 1, 2, 3, 4, 5, 6, 50, 51, 52]:
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()
        now += timedelta(seconds=2)
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "on"
    assert state.attributes["sample_count"] == 3
    assert state.attributes["trailing_sample_count"] == 7


async def test_no_data(hass: HomeAssistant):
    """Test that sample count is limited correctly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    assert state.attributes["sample_count"] == 0
    assert state.attributes["trailing_sample_count"] == 0


async def test_null_new_state(hass: HomeAssistant):
    """Test that sample count is limited correctly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "min_change_amount": 3,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", 1)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", None)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"
    assert state.attributes["sample_count"] == 1
    assert state.attributes["trailing_sample_count"] == 1


async def test_non_numeric(hass: HomeAssistant):
    """Test up anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {"test_anomaly_sensor": {"entity_id": "sensor.test_state"}},
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "Non")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "Numeric")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_missing_attribute(hass: HomeAssistant):
    """Test attribute down anomaly."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {
                    "test_anomaly_sensor": {
                        "entity_id": "sensor.test_state",
                        "attribute": "missing",
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_state", "State", {"attr": "2"})
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "State", {"attr": "1"})
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test_anomaly_sensor")
    assert state.state == "off"


async def test_reload(hass: HomeAssistant):
    """Verify we can reload anomaly sensors."""
    hass.states.async_set("sensor.test_state", 1234)

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {"test_anomaly_sensor": {"entity_id": "sensor.test_state"}},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("binary_sensor.test_anomaly_sensor")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "anomaly/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("binary_sensor.test_anomaly_sensor") is None
    assert hass.states.get("binary_sensor.second_test_anomaly_sensor")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
