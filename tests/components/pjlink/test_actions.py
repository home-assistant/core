"""The test for the pjlink MediaEntity actions."""

from unittest.mock import create_autospec, patch

import pypjlink
from pypjlink.projector import MUTE_AUDIO
import pytest

from homeassistant.components.pjlink.media_player import PjLinkDevice


@pytest.fixture(name="projector_from_address")
def projector_from_address():
    """Create pjlink Projector mock."""

    with patch("pypjlink.Projector.from_address") as from_address:
        constructor = create_autospec(pypjlink.Projector)
        from_address.return_value = constructor.return_value
        yield from_address


@pytest.fixture(name="mocked_projector")
def mocked_projector(projector_from_address):
    """Create pjlink Projector instance mock."""

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

        yield mocked_instance


async def test_turn_off(mocked_projector):
    """Test turning off beamer."""

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)

    projector.turn_off()

    mocked_projector.set_power.assert_called_with("off")


async def test_turn_on(mocked_projector):
    """Test turning on beamer."""

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)

    projector.turn_on()

    mocked_projector.set_power.assert_called_with("on")


async def test_mute(mocked_projector):
    """Test muting beamer."""

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)

    projector.mute_volume(True)

    mocked_projector.set_mute.assert_called_with(MUTE_AUDIO, True)


async def test_unmute(mocked_projector):
    """Test unmuting beamer."""

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)

    projector.mute_volume(False)

    mocked_projector.set_mute.assert_called_with(MUTE_AUDIO, False)


async def test_select_source(mocked_projector):
    """Test selecting source."""

    projector = PjLinkDevice("127.0.0.1", None, None, None, None)
    projector.update()

    projector.select_source("VGA 1")

    mocked_projector.set_input.assert_called_with("VGA", 1)
