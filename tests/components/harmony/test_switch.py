"""Test the Logitech Harmony Hub activity switches."""

from homeassistant.components.harmony.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers import entity_registry as er

from .const import ENTITY_NILE_TV, ENTITY_PLAY_MUSIC, ENTITY_WATCH_TV, HUB_NAME

from tests.common import MockConfigEntry


async def test_switches(harmony_client, mock_hc, hass, mock_write_config):
    """Ensure connection changes are reflected in the switch states."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # check if switch entities are disabled by default
    assert not hass.states.get(ENTITY_WATCH_TV)
    assert not hass.states.get(ENTITY_PLAY_MUSIC)
    assert not hass.states.get(ENTITY_NILE_TV)

    # try enabling one entity
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(ENTITY_WATCH_TV)
    updated_entry = ent_reg.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False
