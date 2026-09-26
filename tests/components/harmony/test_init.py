"""Test init of Logitch Harmony Hub integration."""

import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components.harmony.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import FakeHarmonyClient
from .const import (
    ENTITY_NILE_TV,
    ENTITY_PLAY_MUSIC,
    ENTITY_SELECT,
    ENTITY_WATCH_TV,
    HUB_NAME,
    NILE_TV_ACTIVITY_ID,
    PLAY_MUSIC_ACTIVITY_ID,
    WATCH_TV_ACTIVITY_ID,
)

from tests.common import MockConfigEntry, RegistryEntryWithDefaults, mock_registry


async def test_unique_id_migration(
    mock_hc, hass: HomeAssistant, mock_write_config
) -> None:
    """Test migration of switch unique ids to stable ones."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    mock_registry(
        hass,
        {
            # old format
            ENTITY_WATCH_TV: RegistryEntryWithDefaults(
                entity_id=ENTITY_WATCH_TV,
                unique_id="123443-Watch TV",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # old format, activity name with -
            ENTITY_NILE_TV: RegistryEntryWithDefaults(
                entity_id=ENTITY_NILE_TV,
                unique_id="123443-Nile-TV",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # new format
            ENTITY_PLAY_MUSIC: RegistryEntryWithDefaults(
                entity_id=ENTITY_PLAY_MUSIC,
                unique_id=f"activity_{PLAY_MUSIC_ACTIVITY_ID}",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # old entity which no longer has a matching activity on the hub. skipped.
            "switch.some_other_activity": RegistryEntryWithDefaults(
                entity_id="switch.some_other_activity",
                unique_id="123443-Some Other Activity",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
            # select entity
            ENTITY_SELECT: RegistryEntryWithDefaults(
                entity_id=ENTITY_SELECT,
                unique_id=f"{HUB_NAME}_activities",
                platform="harmony",
                config_entry_id=entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)  # pylint: disable=home-assistant-tests-registry-fixtures

    switch_tv = ent_reg.async_get(ENTITY_WATCH_TV)
    assert switch_tv.unique_id == f"activity_{WATCH_TV_ACTIVITY_ID}"

    switch_nile = ent_reg.async_get(ENTITY_NILE_TV)
    assert switch_nile.unique_id == f"activity_{NILE_TV_ACTIVITY_ID}"

    switch_music = ent_reg.async_get(ENTITY_PLAY_MUSIC)
    assert switch_music.unique_id == f"activity_{PLAY_MUSIC_ACTIVITY_ID}"

    select_activities = ent_reg.async_get(ENTITY_SELECT)
    assert select_activities.unique_id == f"{HUB_NAME}_activities"


@pytest.mark.usefixtures("mock_hc")
async def test_connect_timeout_retries_setup(
    hass: HomeAssistant,
    harmony_client: FakeHarmonyClient,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a hub that does not answer the connection does not hold up setup."""

    async def _never_answers() -> bool:
        await asyncio.Event().wait()
        return True

    harmony_client.connect = _never_answers
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.harmony.data.CONNECT_TIMEOUT", 0):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    harmony_client.close.assert_awaited_once()
