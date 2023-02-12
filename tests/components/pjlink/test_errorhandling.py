"""The test for the pjlink MediaEntity error handling."""

import socket
from unittest.mock import create_autospec, patch

import pypjlink
from pypjlink.projector import ProjectorError
import pytest

import homeassistant.components.media_player as media_player
from homeassistant.components.pjlink.media_player import PjLinkDevice
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


@pytest.fixture(name="projector_from_address")
def projector_from_address():
    """Create pjlink Projector mock."""

    with patch("pypjlink.Projector.from_address") as from_address:
        constructor = create_autospec(pypjlink.Projector)
        from_address.return_value = constructor.return_value
        yield from_address


async def test_api_error(projector_from_address, hass):
    """Test invalid api responses."""

    with assert_setup_component(1, media_player.DOMAIN):
        instance = projector_from_address.return_value

        with instance as mocked_instance:
            mocked_instance.get_name.return_value = "Test"
            mocked_instance.get_inputs.return_value = (
                ("HDMI", 1),
                ("HDMI", 2),
                ("VGA", 1),
            )
            mocked_instance.get_power.side_effect = KeyError("OK")

        assert await async_setup_component(
            hass,
            media_player.DOMAIN,
            {
                media_player.DOMAIN: {
                    "platform": "pjlink",
                    "host": "127.0.0.1",
                }
            },
        )

        await hass.async_block_till_done()

        state = hass.states.get("media_player.test")
        assert state.state == "off"


async def test_update_unavailable(projector_from_address, hass):
    """Test update to a device that is unavailable."""

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
                    "host": "127.0.0.1",
                }
            },
        )

        await hass.async_block_till_done()

        state = hass.states.get("media_player.test")
        assert state.state == "off"

        projector_from_address.side_effect = socket.timeout
        await async_update_entity(hass, "media_player.test")

        state = hass.states.get("media_player.test")
        assert state.state == "unavailable"


async def test_unknown_key_error(projector_from_address):
    """Test unknown projector error."""

    instance = projector_from_address.return_value

    with instance as mocked_instance:
        mocked_instance.get_name.return_value = "Test"
        mocked_instance.get_inputs.return_value = (
            ("HDMI", 1),
            ("HDMI", 2),
            ("VGA", 1),
        )

        mocked_instance.get_power.side_effect = KeyError("Not OK")

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)

    with pytest.raises(KeyError):
        projector.update()


async def test_unavailable_time(projector_from_address):
    """Test unavailable time projector error."""

    instance = projector_from_address.return_value

    with instance as mocked_instance:
        mocked_instance.get_name.return_value = "Test"
        mocked_instance.get_power.return_value = "on"
        mocked_instance.get_mute.return_value = [0, True]
        mocked_instance.get_input.return_value = [0, 1]
        mocked_instance.get_inputs.return_value = (
            ("HDMI", 1),
            ("HDMI", 2),
            ("VGA", 1),
        )

        projector = PjLinkDevice("127.0.0.1", None, None, None, None)
        projector.update()

        assert projector._attr_state == media_player.MediaPlayerState.ON
        assert projector._attr_source is not None
        assert projector._attr_is_volume_muted is not False

        mocked_instance.get_power.side_effect = ProjectorError("unavailable time")
        projector.update()

        assert projector._attr_state == media_player.MediaPlayerState.OFF
        assert projector._attr_source is None
        assert projector._attr_is_volume_muted is False


async def test_unknown_projector_error(projector_from_address):
    """Test unknown projector error."""

    instance = projector_from_address.return_value

    with instance as mocked_instance:
        mocked_instance.get_name.return_value = "Test"
        mocked_instance.get_power.return_value = "on"
        mocked_instance.get_mute.return_value = [0, True]
        mocked_instance.get_input.return_value = [0, 1]
        mocked_instance.get_inputs.return_value = (
            ("HDMI", 1),
            ("HDMI", 2),
            ("VGA", 1),
        )

        projector = PjLinkDevice("127.0.0.1", None, None, None, None)
        projector.update()

        mocked_instance.get_power.side_effect = ProjectorError("Unknown")

        with pytest.raises(ProjectorError):
            projector.update()


async def test_startup_unknown_projector_error(projector_from_address):
    """Test unknown projector error."""

    projector_from_address.side_effect = ProjectorError("Unknown")

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)

    with pytest.raises(ProjectorError):
        projector.update()
