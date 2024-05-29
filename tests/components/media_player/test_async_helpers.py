"""The tests for the Async Media player helper functions."""

import pytest

import homeassistant.components.media_player as mp
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import HomeAssistant


class SimpleMediaPlayer(mp.MediaPlayerEntity):
    """Media player test class."""

    def __init__(self, hass):
        """Initialize the test media player."""
        self.hass = hass
        self._volume = 0
        self._state = STATE_OFF

    @property
    def state(self):
        """State of the player."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return (
            mp.const.MediaPlayerEntityFeature.VOLUME_SET
            | mp.const.MediaPlayerEntityFeature.VOLUME_STEP
            | mp.const.MediaPlayerEntityFeature.PLAY
            | mp.const.MediaPlayerEntityFeature.PAUSE
            | mp.const.MediaPlayerEntityFeature.TURN_OFF
            | mp.const.MediaPlayerEntityFeature.TURN_ON
        )

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume

    def media_play(self):
        """Play the media player."""
        self._state = STATE_PLAYING

    def media_pause(self):
        """Plause the media player."""
        self._state = STATE_PAUSED

    def turn_on(self):
        """Turn on state."""
        self._state = STATE_ON

    def turn_off(self):
        """Turn off state."""
        self._state = STATE_OFF

    def standby(self):
        """Put device in standby."""
        self._state = STATE_STANDBY


class ExtendedMediaPlayer(SimpleMediaPlayer):
    """Media player test class."""

    def volume_up(self):
        """Turn volume up for media player."""
        if self.volume_level < 1:
            self.set_volume_level(min(1, self.volume_level + 0.1))

    def volume_down(self):
        """Turn volume down for media player."""
        if self.volume_level > 0:
            self.set_volume_level(max(0, self.volume_level - 0.1))

    def media_play_pause(self):
        """Play or pause the media player."""
        if self._state == STATE_PLAYING:
            self._state = STATE_PAUSED
        else:
            self._state = STATE_PLAYING

    def toggle(self):
        """Toggle the power on the media player."""
        if self._state in [STATE_OFF, STATE_IDLE, STATE_STANDBY]:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF


class AttrMediaPlayer(SimpleMediaPlayer):
    """Media player setting properties via _attr_*."""

    _attr_volume_step = 0.2


class DescrMediaPlayer(SimpleMediaPlayer):
    """Media player setting properties via entity description."""

    entity_description = mp.MediaPlayerEntityDescription(key="test", volume_step=0.3)


@pytest.fixture(params=[ExtendedMediaPlayer, SimpleMediaPlayer])
def player(hass, request):
    """Return a media player."""
    return request.param(hass)


@pytest.mark.parametrize(
    ("player_class", "volume_step"),
    [
        (ExtendedMediaPlayer, 0.1),
        (SimpleMediaPlayer, 0.1),
        (AttrMediaPlayer, 0.2),
        (DescrMediaPlayer, 0.3),
    ],
)
async def test_volume_up(
    hass: HomeAssistant, player_class: type[mp.MediaPlayerEntity], volume_step: float
) -> None:
    """Test the volume_up and set volume methods."""
    player = player_class(hass)
    assert player.volume_level == 0
    await player.async_set_volume_level(0.5)
    assert player.volume_level == 0.5
    await player.async_volume_up()
    assert player.volume_level == 0.5 + volume_step


@pytest.mark.parametrize(
    ("player_class", "volume_step"),
    [
        (ExtendedMediaPlayer, 0.1),
        (SimpleMediaPlayer, 0.1),
        (AttrMediaPlayer, 0.2),
        (DescrMediaPlayer, 0.3),
    ],
)
async def test_volume_down(
    hass: HomeAssistant, player_class: type[mp.MediaPlayerEntity], volume_step: float
) -> None:
    """Test the volume_down and set volume methods."""
    player = player_class(hass)
    assert player.volume_level == 0
    await player.async_set_volume_level(0.5)
    assert player.volume_level == 0.5
    await player.async_volume_down()
    assert player.volume_level == 0.5 - volume_step


async def test_media_play_pause(player) -> None:
    """Test the media_play_pause method."""
    assert player.state == STATE_OFF
    await player.async_media_play_pause()
    assert player.state == STATE_PLAYING
    await player.async_media_play_pause()
    assert player.state == STATE_PAUSED


async def test_turn_on_off(player) -> None:
    """Test the turn on and turn off methods."""
    assert player.state == STATE_OFF
    await player.async_turn_on()
    assert player.state == STATE_ON
    await player.async_turn_off()
    assert player.state == STATE_OFF


async def test_toggle(player) -> None:
    """Test the toggle method."""
    assert player.state == STATE_OFF
    await player.async_toggle()
    assert player.state == STATE_ON
    await player.async_toggle()
    assert player.state == STATE_OFF
    player.standby()
    assert player.state == STATE_STANDBY
    await player.async_toggle()
    assert player.state == STATE_ON
