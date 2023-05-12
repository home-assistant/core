"""The test for the Template sensor platform."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant import config
from homeassistant.components.template import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.reload import SERVICE_RELOAD
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, get_fixture_path


@pytest.mark.parametrize(("count", "domain"), [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            },
            "template": [
                {
                    "trigger": {"platform": "event", "event_type": "event_1"},
                    "sensor": {
                        "name": "top level",
                        "state": "{{ trigger.event.data.source }}",
                    },
                },
                {
                    "sensor": {
                        "name": "top level state",
                        "state": "{{ states.sensor.top_level.state }} + 2",
                    },
                    "binary_sensor": {
                        "name": "top level state",
                        "state": "{{ states.sensor.top_level.state == 'init' }}",
                    },
                },
            ],
        },
    ],
)
async def test_reloadable(hass: HomeAssistant, start_ha) -> None:
    """Test that we can reload."""
    hass.states.async_set("sensor.test_sensor", "mytest")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.top_level_state").state == "unknown + 2"
    assert hass.states.get("binary_sensor.top_level_state").state == "off"

    hass.bus.async_fire("event_1", {"source": "init"})
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5
    assert hass.states.get("sensor.state").state == "mytest"
    assert hass.states.get("sensor.top_level").state == "init"
    await hass.async_block_till_done()
    assert hass.states.get("sensor.top_level_state").state == "init + 2"
    assert hass.states.get("binary_sensor.top_level_state").state == "on"

    await async_yaml_patch_helper(hass, "sensor_configuration.yaml")
    assert len(hass.states.async_all()) == 4

    hass.bus.async_fire("event_2", {"source": "reload"})
    await hass.async_block_till_done()
    assert hass.states.get("sensor.state") is None
    assert hass.states.get("sensor.top_level") is None
    assert hass.states.get("sensor.watching_tv_in_master_bedroom").state == "off"
    assert float(hass.states.get("sensor.combined_sensor_energy_usage").state) == 0
    assert hass.states.get("sensor.top_level_2").state == "reload"


@pytest.mark.parametrize(("count", "domain"), [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            },
            "template": {
                "trigger": {"platform": "event", "event_type": "event_1"},
                "sensor": {
                    "name": "top level",
                    "state": "{{ trigger.event.data.source }}",
                },
            },
        },
    ],
)
async def test_reloadable_can_remove(hass: HomeAssistant, start_ha) -> None:
    """Test that we can reload and remove all template sensors."""
    hass.states.async_set("sensor.test_sensor", "mytest")
    await hass.async_block_till_done()
    hass.bus.async_fire("event_1", {"source": "init"})
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 3
    assert hass.states.get("sensor.state").state == "mytest"
    assert hass.states.get("sensor.top_level").state == "init"

    await async_yaml_patch_helper(hass, "empty_configuration.yaml")
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            }
        },
    ],
)
async def test_reloadable_stops_on_invalid_config(
    hass: HomeAssistant, start_ha
) -> None:
    """Test we stop the reload if configuration.yaml is completely broken."""
    hass.states.async_set("sensor.test_sensor", "mytest")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2

    await async_yaml_patch_helper(hass, "configuration.yaml.corrupt")
    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2


@pytest.mark.parametrize(("count", "domain"), [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            }
        },
    ],
)
async def test_reloadable_handles_partial_valid_config(
    hass: HomeAssistant, start_ha
) -> None:
    """Test we can still setup valid sensors when configuration.yaml has a broken entry."""
    hass.states.async_set("sensor.test_sensor", "mytest")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all("sensor")) == 2

    await async_yaml_patch_helper(hass, "broken_configuration.yaml")
    assert len(hass.states.async_all("sensor")) == 3

    assert hass.states.get("sensor.state") is None
    assert hass.states.get("sensor.watching_tv_in_master_bedroom").state == "off"
    assert float(hass.states.get("sensor.combined_sensor_energy_usage").state) == 0


@pytest.mark.parametrize(("count", "domain"), [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            }
        },
    ],
)
async def test_reloadable_multiple_platforms(hass: HomeAssistant, start_ha) -> None:
    """Test that we can reload."""
    hass.states.async_set("sensor.test_sensor", "mytest")
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {
                        "value_template": "{{ states.sensor.test_sensor.state }}"
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.state").state == "mytest"
    assert hass.states.get("binary_sensor.state").state == "off"
    assert len(hass.states.async_all()) == 3

    await async_yaml_patch_helper(hass, "sensor_configuration.yaml")
    assert len(hass.states.async_all()) == 4
    assert hass.states.get("sensor.state") is None
    assert hass.states.get("sensor.watching_tv_in_master_bedroom").state == "off"
    assert float(hass.states.get("sensor.combined_sensor_energy_usage").state) == 0
    assert hass.states.get("sensor.top_level_2") is not None


@pytest.mark.parametrize(("count", "domain"), [(1, "sensor")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "sensor": {
                "platform": DOMAIN,
                "sensors": {
                    "state": {"value_template": "{{ 1 }}"},
                },
            }
        },
    ],
)
async def test_reload_sensors_that_reference_other_template_sensors(
    hass: HomeAssistant, start_ha
) -> None:
    """Test that we can reload sensor that reference other template sensors."""
    await async_yaml_patch_helper(hass, "ref_configuration.yaml")
    assert len(hass.states.async_all()) == 3
    await hass.async_block_till_done()

    next_time = dt_util.utcnow() + timedelta(seconds=1.2)
    with patch(
        "homeassistant.helpers.ratelimit.dt_util.utcnow", return_value=next_time
    ):
        async_fire_time_changed(hass, next_time)
        await hass.async_block_till_done()
    assert hass.states.get("sensor.test1").state == "3"
    assert hass.states.get("sensor.test2").state == "1"
    assert hass.states.get("sensor.test3").state == "2"


async def async_yaml_patch_helper(hass, filename):
    """Help update configuration.yaml."""
    yaml_path = get_fixture_path(filename, "template")
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()
