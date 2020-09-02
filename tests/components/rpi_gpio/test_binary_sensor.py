"""The test for the rpi_gpio binary_sensor platform."""
from os import path

from homeassistant import config as hass_config, setup
from homeassistant.components.rpi_gpio import DOMAIN
from homeassistant.const import SERVICE_RELOAD

from tests.async_mock import patch


async def test_reload(hass):
    """Verify we can reload rpi_gpio sensors."""

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "rpi_gpio",
                "ports": {"10": "PIR Office", "11": "PIR Bedroom"},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "rpi_gpio/configuration.yaml",
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
