"""The test for the Template sensor platform."""
from os import path
from unittest.mock import patch

from homeassistant import config
from homeassistant.components.template import DOMAIN, SERVICE_RELOAD
from homeassistant.setup import async_setup_component


async def test_reloadable(hass):
    """Test that we can reload."""
    hass.states.async_set("sensor.test_sensor", "mytest")

    await async_setup_component(
        hass,
        "sensor",
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
    )
    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2

    yaml_path = path.join(
        _get_fixtures_base_path(), "fixtures", "template/sensor_configuration.yaml",
    )
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.state") is None
    assert hass.states.get("sensor.watching_tv_in_master_bedroom").state == "off"
    assert float(hass.states.get("sensor.combined_sensor_energy_usage").state) == 0


async def test_reloadable_can_remove(hass):
    """Test that we can reload and remove all template sensors."""
    hass.states.async_set("sensor.test_sensor", "mytest")

    await async_setup_component(
        hass,
        "sensor",
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
    )
    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2

    yaml_path = path.join(
        _get_fixtures_base_path(), "fixtures", "template/empty_configuration.yaml",
    )
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1


async def test_reloadable_stops_on_invalid_config(hass):
    """Test we stop the reload if configuration.yaml is completely broken."""
    hass.states.async_set("sensor.test_sensor", "mytest")

    await async_setup_component(
        hass,
        "sensor",
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
    )

    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2

    yaml_path = path.join(
        _get_fixtures_base_path(), "fixtures", "template/configuration.yaml.corrupt",
    )
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2


async def test_reloadable_handles_partial_valid_config(hass):
    """Test we can still setup valid sensors when configuration.yaml has a broken entry."""
    hass.states.async_set("sensor.test_sensor", "mytest")

    await async_setup_component(
        hass,
        "sensor",
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
    )

    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.state").state == "mytest"
    assert len(hass.states.async_all()) == 2

    yaml_path = path.join(
        _get_fixtures_base_path(), "fixtures", "template/broken_configuration.yaml",
    )
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.state") is None
    assert hass.states.get("sensor.watching_tv_in_master_bedroom").state == "off"
    assert float(hass.states.get("sensor.combined_sensor_energy_usage").state) == 0


async def test_reloadable_multiple_platforms(hass):
    """Test that we can reload."""
    hass.states.async_set("sensor.test_sensor", "mytest")

    await async_setup_component(
        hass,
        "sensor",
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
    )
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

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.state").state == "mytest"
    assert hass.states.get("binary_sensor.state").state == "off"

    assert len(hass.states.async_all()) == 3

    yaml_path = path.join(
        _get_fixtures_base_path(), "fixtures", "template/sensor_configuration.yaml",
    )
    with patch.object(config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN, SERVICE_RELOAD, {}, blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.state") is None
    assert hass.states.get("sensor.watching_tv_in_master_bedroom").state == "off"
    assert float(hass.states.get("sensor.combined_sensor_energy_usage").state) == 0


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
