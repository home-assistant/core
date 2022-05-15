"""Fixtures for history tests."""
import pytest

from homeassistant.components import history
from homeassistant.components.recorder import filters
from homeassistant.setup import setup_component


@pytest.fixture
def hass_history(hass_recorder):
    """Home Assistant fixture with history."""
    hass = hass_recorder()

    config = history.CONFIG_SCHEMA(
        {
            history.DOMAIN: {
                filters.CONF_INCLUDE: {
                    filters.CONF_DOMAINS: ["media_player"],
                    filters.CONF_ENTITIES: ["thermostat.test"],
                },
                filters.CONF_EXCLUDE: {
                    filters.CONF_DOMAINS: ["thermostat"],
                    filters.CONF_ENTITIES: ["media_player.test"],
                },
            }
        }
    )
    assert setup_component(hass, history.DOMAIN, config)

    yield hass
