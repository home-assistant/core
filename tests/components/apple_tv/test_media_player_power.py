"""Tests for Apple TV media-player power state."""

from __future__ import annotations

from types import SimpleNamespace

from pyatv.const import DeviceState, FeatureName, FeatureState, PowerState

from homeassistant.components.apple_tv import media_player as mp


def _player(
    *, power_state: PowerState, feature_available: bool, playing
) -> mp.AppleTvMediaPlayer:
    # Bypass __init__ to avoid pulling in manager/pyatv; set only what `state` needs.
    player: mp.AppleTvMediaPlayer = object.__new__(mp.AppleTvMediaPlayer)
    player.manager = SimpleNamespace(is_connecting=False)

    def in_state(states, feature):
        if feature != FeatureName.PowerState:
            return False
        # `states` can be a FeatureState or an iterable
        if isinstance(states, (list, tuple, set)):
            return feature_available and FeatureState.Available in states
        return feature_available and states == FeatureState.Available

    player.atv = SimpleNamespace(
        features=SimpleNamespace(in_state=in_state),
        power=SimpleNamespace(power_state=power_state),
    )
    player._playing = playing
    return player


def test_state_off_when_power_off_and_not_playing() -> None:
    """Test state is OFF when power is off and not playing."""
    p = _player(power_state=PowerState.Off, feature_available=True, playing=None)
    assert p.state == mp.MediaPlayerState.OFF


def test_state_on_when_power_on_and_not_playing() -> None:
    """Test state is ON when power is on and not playing."""
    p = _player(power_state=PowerState.On, feature_available=True, playing=None)
    assert p.state == mp.MediaPlayerState.ON


def test_playing_state_takes_precedence_over_power_on() -> None:
    """Test that playing state takes precedence over power on."""
    playing = SimpleNamespace(device_state=DeviceState.Playing)
    p = _player(power_state=PowerState.On, feature_available=True, playing=playing)
    assert p.state == mp.MediaPlayerState.PLAYING


# If the power feature is not available, playback still determines state.


def test_state_comes_from_playback_when_power_feature_unavailable() -> None:
    """If the power feature is not available, playback still determines state."""
    playing = SimpleNamespace(device_state=DeviceState.Playing)
    p = _player(power_state=PowerState.Off, feature_available=False, playing=playing)
    assert p.state == mp.MediaPlayerState.PLAYING


def test_state_unknown_when_power_feature_unavailable_and_not_playing() -> None:
    """If there is no playback and no power feature, state falls back to None (unknown)."""
    p = _player(power_state=PowerState.On, feature_available=False, playing=None)
    # The `state` property returns None here; HA will display this as "unknown".
    # This matches the PR's final return path when power feature is not usable.
    assert p.state is None
