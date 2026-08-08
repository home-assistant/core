"""Test the Bravia TV media player."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.braviatv.const import CONF_USE_PSK, DOMAIN
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.bravia_tv_model"

BRAVIA_SYSTEM_INFO = {
    "product": "TV",
    "region": "XEU",
    "language": "pol",
    "model": "TV-Model",
    "serial": "serial_number",
    "macAddr": "AA:BB:CC:DD:EE:FF",
    "name": "BRAVIA",
    "generation": "5.2.0",
    "area": "POL",
    "cid": "very_unique_string",
}

# "title" is the generic connector name, "label" the name set on the TV itself.
INPUTS = [
    {
        "uri": "extInput:hdmi?port=1",
        "title": "HDMI 1",
        "connection": False,
        "label": "",
        "icon": "meta:hdmi",
    },
    {
        "uri": "extInput:hdmi?port=2",
        "title": "HDMI 2",
        "connection": True,
        "label": "Game console",
        "icon": "meta:hdmi",
    },
]

PLAYING_INFO = {"uri": "extInput:hdmi?port=2", "title": "HDMI 2", "source": "HDMI"}


@pytest.fixture
async def set_play_content(hass: HomeAssistant) -> AsyncGenerator[AsyncMock]:
    """Set up the integration and yield the mocked set_play_content."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="BRAVIA TV-Model",
        data={
            CONF_HOST: "localhost",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_USE_PSK: True,
            CONF_PIN: "12345qwerty",
        },
        unique_id="very_unique_string",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch("pybravia.BraviaClient.get_system_info", return_value=BRAVIA_SYSTEM_INFO),
        patch("pybravia.BraviaClient.get_power_status", return_value="active"),
        patch("pybravia.BraviaClient.get_external_status", return_value=INPUTS),
        patch("pybravia.BraviaClient.get_volume_info", return_value={}),
        patch("pybravia.BraviaClient.get_playing_info", return_value=PLAYING_INFO),
        patch("pybravia.BraviaClient.get_app_list", return_value=[]),
        patch("pybravia.BraviaClient.get_content_list_all", return_value=[]),
        patch("pybravia.BraviaClient.get_command_list", return_value=[]),
        patch("pybravia.BraviaClient.set_play_content") as mock_set_play_content,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_set_play_content


@pytest.mark.usefixtures("set_play_content")
async def test_source_list_prefers_label(hass: HomeAssistant) -> None:
    """Test that an input renamed on the TV is exposed with that name."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    # "HDMI 1" has no label and keeps the generic name, "HDMI 2" was renamed.
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["HDMI 1", "Game console"]
    # The playing input is reported with the same name used in the source list.
    assert state.attributes[ATTR_INPUT_SOURCE] == "Game console"


async def test_select_source_by_label(
    hass: HomeAssistant, set_play_content: AsyncMock
) -> None:
    """Test that selecting a renamed input resolves to the right uri."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "Game console"},
        blocking=True,
    )

    set_play_content.assert_called_once_with("extInput:hdmi?port=2")
