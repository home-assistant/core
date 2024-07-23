"""Test the setup of the Youless integration."""

from homeassistant import setup
from homeassistant.components import youless
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_component


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Check if the setup of the integration succeeds."""

    entry = await init_component(hass)

    assert await setup.async_setup_component(hass, youless.DOMAIN, {})
    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids()) == 19
