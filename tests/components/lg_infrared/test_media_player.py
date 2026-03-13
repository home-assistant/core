"""Tests for the LG Infrared media player platform."""

from __future__ import annotations

from infrared_protocols.codes.lg.tv import LGTVCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_ENTITY_ID, MockInfraredEntity

from tests.common import MockConfigEntry, snapshot_platform

MEDIA_PLAYER_ENTITY_ID = "media_player.lg_tv"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity is created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Verify entity belongs to the correct device
    device_entry = device_registry.async_get_device(
        identifiers={("lg_infrared", mock_config_entry.entry_id)}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_TURN_ON, {}, LGTVCode.POWER),
        (SERVICE_TURN_OFF, {}, LGTVCode.POWER),
        (SERVICE_VOLUME_UP, {}, LGTVCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, LGTVCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, LGTVCode.MUTE),
        (SERVICE_MEDIA_NEXT_TRACK, {}, LGTVCode.CHANNEL_UP),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, LGTVCode.CHANNEL_DOWN),
        (SERVICE_MEDIA_PLAY, {}, LGTVCode.PLAY),
        (SERVICE_MEDIA_PAUSE, {}, LGTVCode.PAUSE),
        (SERVICE_MEDIA_STOP, {}, LGTVCode.STOP),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: LGTVCode,
) -> None:
    """Test each media player action sends the correct IR code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, **service_data},
        blocking=True,
    )

    assert len(mock_infrared_entity.send_command_calls) == 1
    assert mock_infrared_entity.send_command_calls[0] == expected_code


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    # Initially available
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Make IR entity unavailable
    hass.states.async_set(MOCK_INFRARED_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Restore IR entity
    hass.states.async_set(MOCK_INFRARED_ENTITY_ID, "2026-01-01T00:00:00.000")
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
