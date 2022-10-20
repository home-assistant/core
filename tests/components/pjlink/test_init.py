"""The test for the pjlink MediaEntity initialization."""

import socket
from unittest.mock import create_autospec, patch

import pypjlink
import pytest

import homeassistant.components.media_player as media_player
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


@pytest.fixture(name="projector_from_address")
def projector_from_address():
    """Create pjlink Projector mock."""

    with patch("pypjlink.Projector.from_address") as from_address:
        constructor = create_autospec(pypjlink.Projector)
        from_address.return_value = constructor.return_value
        yield from_address


@pytest.mark.parametrize("side_effect", [socket.timeout, OSError])
async def test_offline_initialization(projector_from_address, hass, side_effect):
    """Test initialization of a device that is offline."""

    with assert_setup_component(1, media_player.DOMAIN):
        projector_from_address.side_effect = side_effect

        assert await async_setup_component(
            hass,
            media_player.DOMAIN,
            {
                media_player.DOMAIN: {
                    "platform": "pjlink",
                    "name": "test_offline",
                    "host": "127.0.0.1",
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("media_player.test_offline")
        assert state.state == "unavailable"


async def test_initialization(projector_from_address, hass):
    """Test a device that is available."""

    with assert_setup_component(1, media_player.DOMAIN):
        instance = projector_from_address.return_value

        with instance as mocked_instance:
            mocked_instance.get_name.return_value = "Test"
            mocked_instance.get_inputs.return_value = (
                ("HDMI", 1),
                ("HDMI", 2),
                ("VGA", 1),
            )

        assert await async_setup_component(
            hass,
            media_player.DOMAIN,
            {
                media_player.DOMAIN: {
                    "platform": "pjlink",
                    "name": "test",
                    "host": "127.0.0.1",
                }
            },
        )

        await hass.async_block_till_done()

        state = hass.states.get("media_player.test")
        assert state.state == "off"

        assert "source_list" in state.attributes
        source_list = state.attributes["source_list"]

        assert {"HDMI 1", "HDMI 2", "VGA 1"} == set(source_list)
