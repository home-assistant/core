"""Fixtures for history tests."""
import pytest

from homeassistant.components import history
from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.setup import setup_component


@pytest.fixture
def hass_history(hass_recorder):
    """Home Assistant fixture with history."""
    hass = hass_recorder()

    config = history.CONFIG_SCHEMA(
        {
            history.DOMAIN: {
                CONF_INCLUDE: {
                    CONF_DOMAINS: ["media_player"],
                    CONF_ENTITIES: ["thermostat.test"],
                },
                CONF_EXCLUDE: {
                    CONF_DOMAINS: ["thermostat"],
                    CONF_ENTITIES: ["media_player.test"],
                },
            }
        }
    )
    assert setup_component(hass, history.DOMAIN, config)

    return hass
