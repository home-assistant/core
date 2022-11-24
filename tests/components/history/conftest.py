"""Fixtures for history tests."""
import pytest

from spencerassistant.components import history
from spencerassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from spencerassistant.setup import setup_component


@pytest.fixture
def hass_history(hass_recorder):
    """spencer Assistant fixture with history."""
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

    yield hass
