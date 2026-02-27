"""Fixtures for the media player entity platform tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.media_player import (
    DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockMediaPlayer(MediaPlayerEntity):
    """Mocked media player entity."""

    def __init__(
        self,
        supported_features: MediaPlayerEntityFeature = MediaPlayerEntityFeature(0),
    ) -> None:
        """Initialize the media player."""
        self._volume = 0.0
        self.calls_set_volume = MagicMock()
        self._attr_supported_features = supported_features
        self._attr_has_entity_name = True
        self._attr_name = "test_media_player"
        self._attr_unique_id = "very_unique_media_player_id"
        super().__init__()

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._volume

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._volume = volume
        self.calls_set_volume(volume=volume)


class MockMediaPlayerVolumeUpDown(MockMediaPlayer):
    """Mocked media player entity with custom volume_up/volume_down."""

    def __init__(
        self,
        supported_features: MediaPlayerEntityFeature = MediaPlayerEntityFeature(0),
    ) -> None:
        """Initialize the media player."""
        super().__init__(supported_features)
        self.calls_volume_up = MagicMock()
        self.calls_volume_down = MagicMock()

    def volume_up(self) -> None:
        """Turn volume up for media player."""
        self.calls_volume_up()
        if self.volume_level < 1:
            self.set_volume_level(min(1, self.volume_level + 0.1))

    def volume_down(self) -> None:
        """Turn volume down for media player."""
        self.calls_volume_down()
        if self.volume_level > 0:
            self.set_volume_level(max(0, self.volume_level - 0.1))


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


@pytest.fixture(name="supported_features")
async def media_player_supported_features() -> MediaPlayerEntityFeature:
    """Return the supported features for the test media player entity."""
    return (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )


@pytest.fixture(name="mock_media_player_entity")
async def setup_media_player_platform_test_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    supported_features: MediaPlayerEntityFeature,
) -> MockMediaPlayer:
    """Set up media player entity using an entity platform."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.MEDIA_PLAYER]
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    entity = MockMediaPlayer(supported_features=supported_features)

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test media player platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None

    return entity


@pytest.fixture(name="mock_media_player_custom_vol_entity")
async def setup_media_player_custom_vol_platform_test_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    supported_features: MediaPlayerEntityFeature,
) -> MockMediaPlayerVolumeUpDown:
    """Set up media player entity with custom volume methods."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.MEDIA_PLAYER]
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    entity = MockMediaPlayerVolumeUpDown(supported_features=supported_features)

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test media player platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None

    return entity
