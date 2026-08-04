"""Test the Frontier Silicon switch entity."""

from functools import partial
from unittest.mock import patch

from afsapi import AFSAPI

from homeassistant.components.frontier_silicon.switch import SWITCHES, AFSAPISwitch

from tests.common import MockConfigEntry


class FakeAFSAPISwitches:
    """Fake AFSAPI device which keeps track of switch states."""

    def __init__(self) -> None:
        """Set up default node states."""
        self.node_state_map = {"netRemote.sys.clock.dst": True}

    def get_state(self, node_path: str) -> bool:
        """Get switch state by node name."""
        return self.node_state_map[node_path]

    def set_state(self, node_path: str, new_state: bool) -> None:
        """Set switch state by node name."""
        self.node_state_map[node_path] = new_state


async def test_async_switch_toggle() -> None:
    """Test toggling switch calls the underlying (mocked) AFSAPI functions."""
    fs_device = await AFSAPI.create("http://192.168.1.1:80/device", 1234, 1)
    mock_config_entry = MockConfigEntry()
    fake_device = FakeAFSAPISwitches()
    with (
        patch(
            "afsapi.AFSAPI.get_dst",
            side_effect=partial(fake_device.get_state, "netRemote.sys.clock.dst"),
        ),
        patch(
            "afsapi.AFSAPI.set_dst",
            side_effect=partial(fake_device.set_state, "netRemote.sys.clock.dst"),
        ),
    ):
        for test_switch_description in SWITCHES:
            entity = AFSAPISwitch(mock_config_entry, fs_device, test_switch_description)

            # grab initial state
            await entity.async_update()
            initial_state = entity.is_on

            # toggle initial state
            if initial_state:
                await entity.async_turn_off()
            else:
                await entity.async_turn_on()

            # get and check updated state
            await entity.async_update()
            toggled_state = entity.is_on
            assert initial_state == (not toggled_state)

            # reset state
            if not initial_state:
                await entity.async_turn_off()
            else:
                await entity.async_turn_on()

            # get and check final state
            await entity.async_update()
            final_state = entity.is_on
            assert initial_state == final_state
