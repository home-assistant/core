"""The tests for the generic_thermostat."""
from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.components.climate import DOMAIN
from homeassistant.components.generic_thermostat import (
    DOMAIN as GENERIC_THERMOSTAT_DOMAIN,
)
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


async def test_reload(hass: HomeAssistant) -> None:
    """Test we can reload."""

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            "climate": {
                "platform": "generic_thermostat",
                "name": "test",
                "heater": "switch.any",
                "target_sensor": "sensor.any",
            }
        },
    )

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1
    assert hass.states.get("climate.test") is not None

    yaml_path = get_fixture_path("configuration.yaml", "generic_thermostat")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            GENERIC_THERMOSTAT_DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("climate.test") is None
    assert hass.states.get("climate.reload")
