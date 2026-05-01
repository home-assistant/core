"""Tests for the Marantz Infrared media player platform."""

from infrared_protocols.codes.marantz.pm6006 import MarantzPM6006Code
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockInfraredEntity
from .utils import check_availability_follows_ir_entity

from tests.common import MockConfigEntry, snapshot_platform

MEDIA_PLAYER_ENTITY_ID = "media_player.marantz_amplifier_pm6006"


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

    device_entry = device_registry.async_get_device(
        identifiers={("marantz_infrared", mock_config_entry.entry_id)}
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
        (SERVICE_TURN_ON, {}, MarantzPM6006Code.POWER),
        (SERVICE_TURN_OFF, {}, MarantzPM6006Code.POWER),
        (SERVICE_VOLUME_UP, {}, MarantzPM6006Code.VOLUME_UP),
        (SERVICE_VOLUME_DOWN, {}, MarantzPM6006Code.VOLUME_DOWN),
        (SERVICE_VOLUME_MUTE, {"is_volume_muted": True}, MarantzPM6006Code.MUTE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_action_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
    service: str,
    service_data: dict[str, bool],
    expected_code: MarantzPM6006Code,
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


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("CD", MarantzPM6006Code.SOURCE_CD),
        ("Recorder", MarantzPM6006Code.SOURCE_CDR),
        ("Phono", MarantzPM6006Code.SOURCE_PHONO),
        ("Tuner", MarantzPM6006Code.SOURCE_TUNER),
        ("Coax", MarantzPM6006Code.SOURCE_COAX),
        ("Network", MarantzPM6006Code.SOURCE_NETWORK),
        ("Optical", MarantzPM6006Code.SOURCE_OPTICAL),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_media_player_select_source(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
    source: str,
    expected_code: MarantzPM6006Code,
) -> None:
    """Test selecting a source sends the correct IR code and updates state."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, ATTR_INPUT_SOURCE: source},
        blocking=True,
    )

    assert mock_infrared_entity.send_command_calls == [expected_code]

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_INPUT_SOURCE] == source
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == [
        "CD",
        "Coax",
        "Network",
        "Optical",
        "Phono",
        "Recorder",
        "Tuner",
    ]


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_off_update_assumed_state(
    hass: HomeAssistant,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """Both turn-on and turn-off send POWER but assume opposite states."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"

    assert mock_infrared_entity.send_command_calls == [
        MarantzPM6006Code.POWER,
        MarantzPM6006Code.POWER,
    ]


@pytest.mark.usefixtures("init_integration")
async def test_media_player_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test media player becomes unavailable when IR entity is unavailable."""
    await check_availability_follows_ir_entity(hass, MEDIA_PLAYER_ENTITY_ID)


async def test_toggle_flips_between_commands(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_infrared_entity: MockInfraredEntity,
) -> None:
    """The RC-5 toggle bit must alternate so the receiver sees distinct presses."""
    for expected_toggle in (1, 0, 1, 0):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_UP,
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
            blocking=True,
        )
        assert init_integration.runtime_data.toggle == expected_toggle

    assert len(mock_infrared_entity.send_command_calls) == 4
