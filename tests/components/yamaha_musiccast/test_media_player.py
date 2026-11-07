"""Test the media player platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
)
from homeassistant.components.yamaha_musiccast.const import (
    CONF_HIDDEN_SOURCES,
    DEFAULT_ZONE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

MAIN_ENTITY_ID = "media_player.main_musiccast"


async def test_source_list_shows_all_sources_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_musiccast_device
) -> None:
    """Test every known source is listed when none are hidden."""
    mock_config_entry.add_to_hass(hass)
    # Work around the zone always reporting MediaPlayerState.OFF: the
    # integration's state property compares zone.power to the string "on",
    # while aiomusiccast types it as a bool. Unrelated pre-existing issue.
    mock_musiccast_device.data.zones[DEFAULT_ZONE].power = "on"
    # Avoid hashing the unset MagicMock media_image_url once the player is on.
    mock_musiccast_device.media_image_url = None

    with patch(
        "homeassistant.components.yamaha_musiccast.PLATFORMS", [Platform.MEDIA_PLAYER]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state is not None
    assert sorted(state.attributes[ATTR_INPUT_SOURCE_LIST]) == [
        "Bluetooth",
        "NET RADIO",
    ]
    assert state.attributes[ATTR_INPUT_SOURCE] == "NET RADIO"


@pytest.mark.usefixtures("mock_musiccast_device")
async def test_source_list_excludes_hidden_sources(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a hidden source is excluded from source_list."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_HIDDEN_SOURCES: ["bluetooth"]}
    )

    with patch(
        "homeassistant.components.yamaha_musiccast.PLATFORMS", [Platform.MEDIA_PLAYER]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["NET RADIO"]


async def test_hidden_current_source_still_reported(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_musiccast_device
) -> None:
    """Test the active source is still reported even if it is hidden."""
    mock_config_entry.add_to_hass(hass)
    # See comment in test_source_list_shows_all_sources_by_default.
    mock_musiccast_device.data.zones[DEFAULT_ZONE].power = "on"
    mock_musiccast_device.media_image_url = None
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_HIDDEN_SOURCES: ["net_radio"]}
    )

    with patch(
        "homeassistant.components.yamaha_musiccast.PLATFORMS", [Platform.MEDIA_PLAYER]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["Bluetooth"]
    assert state.attributes[ATTR_INPUT_SOURCE] == "NET RADIO"
