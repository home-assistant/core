"""Test squeezebox update platform."""

import copy
from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import FAKE_QUERY_RESPONSE, setup_mocked_integration


async def test_update_lms(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.UPDATE],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("update.fakelib_lyrion_music_server")

    assert state is not None
    assert state.state == "on"


async def test_update_plugins(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test binary sensor states and attributes."""

    # Setup component
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.UPDATE],
        ),
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=copy.deepcopy(FAKE_QUERY_RESPONSE),
        ),
    ):
        await setup_mocked_integration(hass)
    state = hass.states.get("update.fakelib_updated_plugins")

    assert state is not None
    assert state.state == "on"
