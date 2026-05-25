"""Tests for the Samsung Infrared media player platform."""

from infrared_protocols.codes.samsung.tv import SamsungTVCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.components.samsung_infrared.const import SOURCE_MAP
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared.common import MockInfraredEmitterEntity

MEDIA_PLAYER_ENTITY_ID = "media_player.samsung_tv"


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
        identifiers={("samsung_infrared", mock_config_entry.entry_id)}
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
        (SERVICE_TURN_ON, {}, SamsungTVCode.POWER_ON),
        (SERVICE_TURN_OFF, {}, SamsungTVCode.POWER_OFF),
        (SERVICE_VOLUME_UP, {}, SamsungTVCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, SamsungTVCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, SamsungTVCode.MUTE),
        (SERVICE_MEDIA_NEXT_TRACK, {}, SamsungTVCode.CHANNEL_UP),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, SamsungTVCode.CHANNEL_DOWN),
        (SERVICE_MEDIA_PLAY, {}, SamsungTVCode.PLAY),
        (SERVICE_MEDIA_PAUSE, {}, SamsungTVCode.PAUSE),
        (SERVICE_MEDIA_STOP, {}, SamsungTVCode.STOP),
        (SERVICE_SELECT_SOURCE, {"source": "tv"}, SamsungTVCode.TV),
        (SERVICE_SELECT_SOURCE, {"source": "hdmi_1"}, SamsungTVCode.HDMI_1),
        (SERVICE_SELECT_SOURCE, {"source": "hdmi_2"}, SamsungTVCode.HDMI_2),
        (SERVICE_SELECT_SOURCE, {"source": "hdmi_3"}, SamsungTVCode.HDMI_3),
        (SERVICE_SELECT_SOURCE, {"source": "hdmi_4"}, SamsungTVCode.HDMI_4),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: SamsungTVCode,
) -> None:
    """Test each media player action sends the correct IR code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, **service_data},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert (
        mock_infrared_emitter_entity.send_command_calls[0] == expected_code.to_command()
    )

    # Verify source attribute is updated for SELECT_SOURCE calls
    if service == SERVICE_SELECT_SOURCE:
        state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
        assert state is not None
        assert state.attributes.get("source") == service_data["source"]


@pytest.mark.usefixtures("init_integration")
async def test_select_invalid_source(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test selecting an invalid source raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, "source": "invalid_source"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == "samsung_infrared"
    assert exc_info.value.translation_key == "invalid_source"

    placeholders = exc_info.value.translation_placeholders
    assert placeholders["invalid_source"] == "invalid_source"
    assert set(placeholders["valid_sources"].split(", ")) == set(SOURCE_MAP.keys())

    # Verify no command was sent
    assert len(mock_infrared_emitter_entity.send_command_calls) == 0
