"""Test init of Logitch Harmony Hub integration."""
from homeassistant.components.harmony.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .const import (
    ENTITY_NILE_TV,
    ENTITY_PLAY_MUSIC,
    ENTITY_WATCH_TV,
    HUB_NAME,
    NILE_TV_ACTIVITY_ID,
    PLAY_MUSIC_ACTIVITY_ID,
    WATCH_TV_ACTIVITY_ID,
)

from tests.common import MockConfigEntry, mock_registry


async def test_unique_id_migration(mock_hc, hass, mock_write_config):
    """Test migration of switch unique ids to stable ones."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    mock_registry(
        hass,
        {
            # old format
            ENTITY_WATCH_TV: er.RegistryEntry(
                entity_id=ENTITY_WATCH_TV,
                unique_id="123443-Watch TV",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # old format, activity name with -
            ENTITY_NILE_TV: er.RegistryEntry(
                entity_id=ENTITY_NILE_TV,
                unique_id="123443-Nile-TV",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # new format
            ENTITY_PLAY_MUSIC: er.RegistryEntry(
                entity_id=ENTITY_PLAY_MUSIC,
                unique_id=f"activity_{PLAY_MUSIC_ACTIVITY_ID}",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # old entity which no longer has a matching activity on the hub. skipped.
            "switch.some_other_activity": er.RegistryEntry(
                entity_id="switch.some_other_activity",
                unique_id="123443-Some Other Activity",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    switch_tv = ent_reg.async_get(ENTITY_WATCH_TV)
    assert switch_tv.unique_id == f"activity_{WATCH_TV_ACTIVITY_ID}"

    switch_nile = ent_reg.async_get(ENTITY_NILE_TV)
    assert switch_nile.unique_id == f"activity_{NILE_TV_ACTIVITY_ID}"

    switch_music = ent_reg.async_get(ENTITY_PLAY_MUSIC)
    assert switch_music.unique_id == f"activity_{PLAY_MUSIC_ACTIVITY_ID}"
