"""Setup/unload tests for the Color helper config entry."""

from homeassistant.components.color.const import (
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_XY_COLOR,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_MODE,
    DOMAIN,
    KIND_CHROMATIC,
    MODE_CHROMATIC,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "color.couch_color"


async def test_setup_and_unload_chromatic_entry(hass: HomeAssistant) -> None:
    """A chromatic config entry produces a single color.* entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Couch Color",
        data={
            CONF_NAME: "Couch Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
            CONF_INITIAL_COLOR: "#FF8000",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state.startswith("#")
    assert state.attributes[ATTR_KIND] == KIND_CHROMATIC
    assert ATTR_RGB_COLOR in state.attributes
    assert ATTR_XY_COLOR in state.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
