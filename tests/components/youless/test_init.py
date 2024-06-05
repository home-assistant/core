"""Test the setup of the Youless integration."""

import unittest.mock

from homeassistant import setup
from homeassistant.components import youless
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _mock_init(*args):
    youless_api = args[0]
    youless_api.initialize = lambda: None
    youless_api.update = lambda: None
    youless_api._model = "LS120"
    youless_api._cache_data = ()


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Check if the setup of the integration succeeds."""
    entry = MockConfigEntry(
        domain=youless.DOMAIN,
        title="localhost",
        data={CONF_HOST: "localhost", CONF_DEVICE: "localhost"},
    )
    entry.add_to_hass(hass)

    unittest.mock.patch("youless_api.YoulessAPI.__init__", _mock_init).start()

    assert await setup.async_setup_component(hass, youless.DOMAIN, {})
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids()) == 19
