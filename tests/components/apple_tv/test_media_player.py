"""Test Apple TV media player."""

import asyncio

from pyatv.const import FeatureName, FeatureState
from pyatv.interface import (
    AppleTV,
    Apps,
    Audio,
    BaseService,
    DeviceInfo,
    FeatureInfo,
    Features,
    Keyboard,
    Metadata,
    Power,
    PushUpdater,
    RemoteControl,
    Stream,
    UserAccounts,
)
from pyatv.settings import Settings

from homeassistant.components.apple_tv.media_player import AppleTvMediaPlayer
from homeassistant.core import HomeAssistant


class _MockUnknownFeatures(Features):
    def get_feature(self, feature_name: FeatureName) -> FeatureInfo:
        return FeatureInfo(state=FeatureState.Unknown)


class _MockAvailableFeatures(Features):
    def get_feature(self, feature_name: FeatureName) -> FeatureInfo:
        return FeatureInfo(state=FeatureState.Available)


class _MockUnavailableFeatures(Features):
    def get_feature(self, feature_name: FeatureName) -> FeatureInfo:
        return FeatureInfo(state=FeatureState.Unavailable)


class _MockAppleTV(AppleTV):
    expected_features = None

    async def connect(self) -> None:
        pass

    def close(self) -> set[asyncio.Task]:
        pass

    @property
    def settings(self) -> Settings:
        pass

    @property
    def device_info(self) -> DeviceInfo:
        pass

    @property
    def service(self) -> BaseService:
        pass

    @property
    def remote_control(self) -> RemoteControl:
        pass

    @property
    def metadata(self) -> Metadata:
        pass

    @property
    def push_updater(self) -> PushUpdater:
        pass

    @property
    def stream(self) -> Stream:
        pass

    @property
    def power(self) -> Power:
        pass

    @property
    def features(self) -> Features:
        return self.expected_features

    @property
    def apps(self) -> Apps:
        pass

    @property
    def user_accounts(self) -> UserAccounts:
        pass

    @property
    def audio(self) -> Audio:
        pass

    @property
    def keyboard(self) -> Keyboard:
        pass


async def test_is_feature_available(hass: HomeAssistant) -> None:
    """Test when a feature is available."""
    media_player = AppleTvMediaPlayer("test_player", "test_player_id", None)
    media_player._playing = True
    media_player.atv = _MockAppleTV()
    media_player.atv.expected_features = _MockAvailableFeatures()
    assert media_player._is_feature_available(FeatureName.Artwork)


def test_is_feature_available_unknown(hass: HomeAssistant) -> None:
    """Test when a feature is unknown, and may be available or not."""
    media_player = AppleTvMediaPlayer("test_player", "test_player_id", None)
    media_player._playing = True
    media_player.atv = _MockAppleTV()
    media_player.atv.expected_features = _MockUnknownFeatures()
    assert media_player._is_feature_available(FeatureName.Artwork)


def test_is_feature_available_unavailable(hass: HomeAssistant) -> None:
    """Test when a known feature is unavailable."""
    media_player = AppleTvMediaPlayer("test_player", "test_player_id", None)
    media_player._playing = True
    media_player.atv = _MockAppleTV()
    media_player.atv.expected_features = _MockUnavailableFeatures()
    assert not media_player._is_feature_available(FeatureName.Artwork)


def test_is_feature_available_not_playing(hass: HomeAssistant) -> None:
    """Test when a feature is not available because the player is not playing."""
    media_player = AppleTvMediaPlayer("test_player", "test_player_id", None)
    # media_player._playing = True
    media_player.atv = _MockAppleTV()
    media_player.atv.expected_features = _MockAvailableFeatures()
    assert not media_player._is_feature_available(FeatureName.Artwork)
