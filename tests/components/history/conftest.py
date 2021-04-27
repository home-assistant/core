"""Fixtures for history tests."""
import pytest

from homeassistant.components import history
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant, init_recorder_component


@pytest.fixture
def hass_recorder():
    """Home Assistant fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Set up with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


@pytest.fixture
def hass_history(hass_recorder):
    """Home Assistant fixture with history."""
    hass = hass_recorder()

    config = history.CONFIG_SCHEMA(
        {
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
