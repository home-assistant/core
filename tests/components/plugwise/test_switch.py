"""Tests for the Plugwise switch integration."""

from plugwise.exceptions import PlugwiseException

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.plugwise.common import async_init_integration


async def test_adam_climate_switch_entities(hass, mock_smile_adam):
    """Test creation of climate related switch entities."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("switch.cv_pomp")
    assert str(state.state) == "on"

    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "on"


async def test_adam_climate_switch_negative_testing(hass, mock_smile_adam):
    """Test exceptions of climate related switch entities."""
    mock_smile_adam.set_switch_state.side_effect = PlugwiseException
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.cv_pomp"},
        blocking=True,
    )
    state = hass.states.get("switch.cv_pomp")
    assert str(state.state) == "on"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fibaro_hc2"},
        blocking=True,
    )
    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "on"


async def test_adam_climate_switch_changes(hass, mock_smile_adam):
    """Test changing of climate related switch entities."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.cv_pomp"},
        blocking=True,
    )
    state = hass.states.get("switch.cv_pomp")
    assert str(state.state) == "off"

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.fibaro_hc2"},
        blocking=True,
    )
    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "off"

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.fibaro_hc2"},
        blocking=True,
    )
    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "on"


async def test_stretch_switch_entities(hass, mock_stretch):
    """Test creation of climate related switch entities."""
    entry = await async_init_integration(hass, mock_stretch)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("switch.koelkast_92c4a")
    assert str(state.state) == "on"

    state = hass.states.get("switch.droger_52559")
    assert str(state.state) == "on"


async def test_stretch_switch_changes(hass, mock_stretch):
    """Test changing of power related switch entities."""
    entry = await async_init_integration(hass, mock_stretch)
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.koelkast_92c4a"},
        blocking=True,
    )

    state = hass.states.get("switch.koelkast_92c4a")
    assert str(state.state) == "off"

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.droger_52559"},
        blocking=True,
    )
    state = hass.states.get("switch.droger_52559")
    assert str(state.state) == "off"

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.droger_52559"},
        blocking=True,
    )
    state = hass.states.get("switch.droger_52559")
    assert str(state.state) == "on"


async def test_unique_id_migration_plug_relay(hass, mock_smile_adam):
    """Test unique ID migration of -plugs to -relay."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": "1.1.1.1", "password": "test-password"}
    )
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    # Entry to migrate
    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "21f2b542c49845e6bb416884c55778d6-plug",
        config_entry=entry,
        suggested_object_id="playstation_smart_plug",
        disabled_by=None,
    )
    # Entry not needing migration
    registry.async_get_or_create(
        SWITCH_DOMAIN,
        DOMAIN,
        "675416a629f343c495449970e2ca37b5-relay",
        config_entry=entry,
        suggested_object_id="router",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.playstation_smart_plug") is not None
    assert hass.states.get("switch.router") is not None

    entity_entry = registry.async_get("switch.playstation_smart_plug")
    assert entity_entry
    assert entity_entry.unique_id == "21f2b542c49845e6bb416884c55778d6-relay"

    entity_entry = registry.async_get("switch.router")
    assert entity_entry
    assert entity_entry.unique_id == "675416a629f343c495449970e2ca37b5-relay"
