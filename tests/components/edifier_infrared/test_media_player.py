"""Tests for the Edifier Infrared media player platform."""

from infrared_protocols.codes.edifier.models import EdifierCommandSet, EdifierModel
from infrared_protocols.codes.edifier.r1700bt import EdifierR1700BTCode
from infrared_protocols.codes.edifier.rc20g import EdifierRC20GCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.edifier_infrared.const import (
    CONF_COMMAND_SET,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
)
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import MockInfraredEmitterEntity

MEDIA_PLAYER_ENTITY_ID = "media_player.edifier_r1700bt"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.MEDIA_PLAYER]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity is created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "service_data", "expected_code"),
    [
        (SERVICE_TURN_ON, {}, EdifierR1700BTCode.POWER),
        (SERVICE_TURN_OFF, {}, EdifierR1700BTCode.POWER),
        (SERVICE_VOLUME_UP, {}, EdifierR1700BTCode.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, EdifierR1700BTCode.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, EdifierR1700BTCode.MUTE),
        (SERVICE_MEDIA_PLAY, {}, EdifierR1700BTCode.PLAY_PAUSE),
        (SERVICE_MEDIA_PAUSE, {}, EdifierR1700BTCode.PLAY_PAUSE),
        (SERVICE_MEDIA_NEXT_TRACK, {}, EdifierR1700BTCode.FORWARD),
        (SERVICE_MEDIA_PREVIOUS_TRACK, {}, EdifierR1700BTCode.BACK),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: EdifierR1700BTCode,
) -> None:
    """Test each media player action sends the correct IR code."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, **service_data},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] == expected_code


@pytest.mark.parametrize(
    "mock_config_entry",
    [
        MockConfigEntry(
            domain=DOMAIN,
            entry_id="01JTEST0000000000000000001",
            title="Edifier RC20G via Test IR emitter",
            data={
                CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
                CONF_MODEL: EdifierModel.RC20G.value,
                CONF_COMMAND_SET: EdifierCommandSet.RC20G.value,
            },
            unique_id=f"rc20g_{EMITTER_ENTITY_ID}",
        )
    ],
)
@pytest.mark.parametrize(
    ("service", "expected_codes"),
    [
        (
            SERVICE_VOLUME_UP,
            (EdifierRC20GCode.VOLUME_UP_LEFT, EdifierRC20GCode.VOLUME_UP_RIGHT),
        ),
        (
            SERVICE_VOLUME_DOWN,
            (EdifierRC20GCode.VOLUME_DOWN_LEFT, EdifierRC20GCode.VOLUME_DOWN_RIGHT),
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_rc20g_volume_sends_left_and_right_codes(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    expected_codes: tuple[EdifierRC20GCode, ...],
) -> None:
    """Test that RC20G volume up/down send both left and right channel codes."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "media_player.edifier_rc20g"},
        blocking=True,
    )

    assert tuple(mock_infrared_emitter_entity.send_command_calls) == expected_codes


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, MEDIA_PLAYER_ENTITY_ID, EMITTER_ENTITY_ID
    )
