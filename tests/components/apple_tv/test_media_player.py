"""Tests for apple_tv grouping helpers and methods."""

from unittest.mock import AsyncMock, Mock

from pyatv.interface import AppleTV
import pytest

from homeassistant.components.apple_tv.const import DOMAIN
from homeassistant.components.apple_tv.media_player import AppleTvMediaPlayer
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry


@pytest.fixture
def create_player(hass: HomeAssistant, entity_registry: EntityRegistry):
    """Create a mock Apple TV media player for testing."""

    async def create(name: str) -> AppleTvMediaPlayer:
        unique_id = f"{name}-uid"
        output_device_id = f"{name}-output-device-id"

        cfg = MockConfigEntry(
            domain=DOMAIN,
            unique_id=unique_id,
            data={"output_device_id": output_device_id, "name": name},
            state=ConfigEntryState.LOADED,
        )
        cfg.add_to_hass(hass)

        ent = entity_registry.async_get_or_create(
            MEDIA_PLAYER_DOMAIN, DOMAIN, cfg.unique_id, config_entry=cfg
        )

        player = AppleTvMediaPlayer(name, cfg.unique_id, Mock(config_entry=cfg))
        player.atv = AsyncMock(wraps=AppleTV)
        player.atv.audio.output_devices = []
        player.hass = hass
        player.entity_id = ent.entity_id

        async def set_output_devices(*devices):
            new_devices = [Mock(identifier=ident) for ident in devices]
            old_devices = player.atv.audio.output_devices
            player.atv.audio.output_devices = new_devices
            player.outputdevices_update(old_devices, new_devices)

        player.atv.audio.set_output_devices = AsyncMock(side_effect=set_output_devices)
        return player

    return create


async def test_async_join_players(hass: HomeAssistant, create_player) -> None:
    """Test media players are joined and atv is called with the correct output device ids."""
    player_1 = await create_player("player_1")
    player_2 = await create_player("player_2")

    await player_1.async_join_players([player_1.entity_id, player_2.entity_id])

    player_1.atv.audio.set_output_devices.assert_called_with(
        "player_1-output-device-id", "player_2-output-device-id"
    )
    assert player_1._attr_group_members == [player_1.entity_id, player_2.entity_id]


async def test_async_join_players_throws(hass: HomeAssistant, create_player) -> None:
    """Test that joining throws if incompatible entity_ids are passed, yet updates group_member with successfully joined entities."""
    player_1 = await create_player("player_1")
    player_2 = await create_player("player_2")

    with pytest.raises(ServiceValidationError):
        await player_1.async_join_players(
            [player_1.entity_id, player_2.entity_id, "non-existing-entity-id"]
        )

    # we still expect the valid entities to be captured and joined
    player_1.atv.audio.set_output_devices.assert_called_with(
        "player_1-output-device-id", "player_2-output-device-id"
    )
    assert player_1._attr_group_members == [player_1.entity_id, player_2.entity_id]


async def test_outputdevices_update(hass: HomeAssistant, create_player) -> None:
    """Test when atv signals an outputdevice_update, the group_members are updated."""
    player_1 = await create_player("player_1")
    player_2 = await create_player("player_2")

    player_1.atv.audio.output_devices = [
        Mock(identifier="player_1-output-device-id"),
        Mock(identifier="player_2-output-device-id"),
        Mock(identifier="non-hass-player-output-device-id"),
    ]

    player_1.outputdevices_update([], [])
    await hass.async_block_till_done()

    assert player_1._attr_group_members == [player_1.entity_id, player_2.entity_id]
