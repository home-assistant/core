"""Tests for the Sony TV RS-232 integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry
from sony_tv_rs232 import InputSource, PowerState, SoundMode, TVState

from homeassistant.core import HomeAssistant

MOCK_PORT = "/dev/ttyUSB0"


def default_state() -> TVState:
    """Return a TVState for a TV that is on."""
    return TVState(
        power=PowerState.ON,
        input_source=InputSource.HDMI1,
        volume=20,
        audio_mute=False,
        sound_mode=SoundMode.STANDARD,
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration from a config entry."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def mock_state_update(tv: MagicMock, state: TVState | None) -> None:
    """Push a state notification to the TV's subscribers (None = link dropped)."""
    tv.connected = state is not None
    if state is not None:
        tv.state = state
    for subscription in tv.subscribe.call_args_list:
        subscription.args[0](state)
