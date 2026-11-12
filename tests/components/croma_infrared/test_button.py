"""Tests for the Croma Infrared button platform."""

from infrared_protocols.codes.croma.tv import CromaTVCode
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

BUTTON_ENTITY_ID_POWER = "button.croma_tv_power"
MEDIA_PLAYER_ENTITY_ID = "media_player.croma_tv"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all button entities are created with the correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        ("croma_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.croma_tv_power", CromaTVCode.POWER),
        ("button.croma_tv_up", CromaTVCode.UP),
        ("button.croma_tv_down", CromaTVCode.DOWN),
        ("button.croma_tv_left", CromaTVCode.LEFT),
        ("button.croma_tv_right", CromaTVCode.RIGHT),
        ("button.croma_tv_ok", CromaTVCode.OK),
        ("button.croma_tv_back", CromaTVCode.BACK),
        ("button.croma_tv_exit", CromaTVCode.EXIT),
        ("button.croma_tv_home", CromaTVCode.HOME),
        ("button.croma_tv_menu", CromaTVCode.MENU),
        ("button.croma_tv_settings", CromaTVCode.SETTINGS),
        ("button.croma_tv_apps", CromaTVCode.APPS),
        ("button.croma_tv_input", CromaTVCode.SOURCE),
        ("button.croma_tv_info", CromaTVCode.INFO),
        ("button.croma_tv_guide", CromaTVCode.EPG),
        ("button.croma_tv_account", CromaTVCode.ACCOUNT),
        ("button.croma_tv_voice", CromaTVCode.VOICE),
        ("button.croma_tv_subtitles", CromaTVCode.SUBTITLES),
        ("button.croma_tv_program_up", CromaTVCode.PROGRAM_UP),
        ("button.croma_tv_program_down", CromaTVCode.PROGRAM_DOWN),
        ("button.croma_tv_fast_forward", CromaTVCode.FAST_FORWARD),
        ("button.croma_tv_rewind", CromaTVCode.REWIND),
        ("button.croma_tv_free_hotkey", CromaTVCode.FREE_HOTKEY),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: CromaTVCode,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.parametrize("restored_state", [MediaPlayerState.ON, MediaPlayerState.OFF])
@pytest.mark.usefixtures("mock_croma_to_command")
async def test_power_button_keeps_media_player_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    restored_state: MediaPlayerState,
) -> None:
    """Test the power button sends the toggle without changing the assumed state."""
    mock_restore_cache(hass, [State(MEDIA_PLAYER_ENTITY_ID, restored_state)])

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: BUTTON_ENTITY_ID_POWER},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [CromaTVCode.POWER]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state
    assert state.state == restored_state


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test a button becomes unavailable when the IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, BUTTON_ENTITY_ID_POWER, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )
