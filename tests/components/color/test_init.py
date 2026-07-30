"""Setup/unload tests for the Color helper config entry."""

from homeassistant.components.color.const import (
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_SOURCE_HEX,
    ATTR_XY_COLOR,
    CONF_INITIAL_COLOR,
    CONF_INITIAL_KELVIN,
    CONF_INITIAL_MODE,
    DEFAULT_KELVIN,
    DOMAIN,
    KIND_CHROMATIC,
    KIND_WHITE,
    MODE_CHROMATIC,
    MODE_WHITE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def test_white_entry_with_invalid_kelvin_falls_back(hass: HomeAssistant) -> None:
    """An unparsable stored kelvin falls back to the default white."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Couch Color",
        data={
            CONF_NAME: "Couch Color",
            CONF_INITIAL_MODE: MODE_WHITE,
            CONF_INITIAL_KELVIN: "warmish",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_KIND] == KIND_WHITE
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == DEFAULT_KELVIN


async def test_chromatic_entry_without_initial_color(hass: HomeAssistant) -> None:
    """A chromatic entry without an initial color uses the default, no source hex."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Couch Color",
        data={
            CONF_NAME: "Couch Color",
            CONF_INITIAL_MODE: MODE_CHROMATIC,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_KIND] == KIND_CHROMATIC
    assert state.attributes[ATTR_SOURCE_HEX] is None


async def test_registry_entry_linked_to_config_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """The entity registry entry is linked to and cleaned up with the entry."""
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

    registry_entry = entity_registry.async_get(ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.config_entry_id == entry.entry_id

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(ENTITY_ID) is None
    assert hass.states.get(ENTITY_ID) is None
