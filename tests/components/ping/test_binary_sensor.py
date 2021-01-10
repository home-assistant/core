"""The test for the ping binary_sensor platform."""
from os import path
from unittest.mock import patch

from homeassistant import config as hass_config, setup
from homeassistant.components.ping import DOMAIN
from homeassistant.const import SERVICE_RELOAD


async def test_reload(hass):
    """Verify we can reload trend sensors."""

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "ping",
                "name": "test",
                "host": "127.0.0.1",
                "count": 1,
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "ping/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test") is None
    assert hass.states.get("binary_sensor.test2")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
