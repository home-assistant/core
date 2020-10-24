import pytest

from homeassistant.components import history
from homeassistant.setup import setup_component
from tests.components.recorder.conftest import hass_recorder


@pytest.fixture
def hass_history(hass_recorder):
    hass = hass_recorder()

    config = history.CONFIG_SCHEMA(
        {
            # ha.DOMAIN: {},
            history.DOMAIN: {
                history.CONF_INCLUDE: {
                    history.CONF_DOMAINS: ["media_player"],
                    history.CONF_ENTITIES: ["thermostat.test"],
                },
                history.CONF_EXCLUDE: {
                    history.CONF_DOMAINS: ["thermostat"],
                    history.CONF_ENTITIES: ["media_player.test"],
                },
            }
        }
    )
    assert setup_component(hass, history.DOMAIN, config)

    yield hass
