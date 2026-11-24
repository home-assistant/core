"""Tests for the BenQ Projector Infrared button platform."""

import asyncio
from unittest.mock import patch

from infrared_protocols.codes.benq.projector import BenQProjectorCode
from infrared_protocols.commands.nec import NECCommand
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.benq_projector_infrared import PLATFORMS
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerService,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform, TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

MEDIA_PLAYER_ENTITY_ID = "media_player.benq_projector"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    """Press a button."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the button entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        ("button.benq_projector_menu", BenQProjectorCode.MENU),
        ("button.benq_projector_cursor_up", BenQProjectorCode.UP),
        ("button.benq_projector_enter", BenQProjectorCode.ENTER),
        ("button.benq_projector_picture_mode", BenQProjectorCode.PICTURE_MODE),
        ("button.benq_projector_aspect_ratio", BenQProjectorCode.ASPECT),
        ("button.benq_projector_hdr", BenQProjectorCode.HDR),
        ("button.benq_projector_play", BenQProjectorCode.PLAY),
        ("button.benq_projector_keystone_up", BenQProjectorCode.KEYSTONE_UP),
        ("button.benq_projector_test_pattern", BenQProjectorCode.TEST_PATTERN),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: BenQProjectorCode,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await _press(hass, entity_id)

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.parametrize(
    ("entity_id", "enabled"),
    [
        ("button.benq_projector_menu", True),
        ("button.benq_projector_light_mode", True),
        ("button.benq_projector_freeze", False),
        ("button.benq_projector_hdr", False),
        ("button.benq_projector_play", False),
        ("button.benq_projector_keystone_up", False),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_buttons_enabled_by_default(
    entity_registry: er.EntityRegistry, entity_id: str, enabled: bool
) -> None:
    """Keys that not every projector has are disabled by default."""
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert (entity_entry.disabled_by is None) is enabled


@pytest.mark.usefixtures("init_integration")
async def test_no_buttons_for_media_player_functions(
    entity_registry: er.EntityRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Power, volume, mute and the inputs are left to the media player."""
    keys = {
        entry.unique_id.removeprefix(f"{mock_config_entry.entry_id}_")
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert not keys & {
        "power",
        "power_on",
        "power_off",
        "volume_up",
        "volume_down",
        "mute",
        "source",
        "hdmi_1",
    }


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test buttons become unavailable when the IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, "button.benq_projector_menu", [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )


@pytest.mark.parametrize("platforms", [PLATFORMS])
@pytest.mark.usefixtures("init_integration")
async def test_button_refused_while_warming_up(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Buttons share the warm-up with the media player of the same projector."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        MediaPlayerService.TURN_ON,
        {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
        blocking=True,
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press(hass, "button.benq_projector_menu")

    assert exc_info.value.translation_key == "warming_up"
    assert mock_infrared_emitter_entity.send_command_calls == [
        BenQProjectorCode.POWER_ON
    ]


@pytest.mark.parametrize("has_receiver_entity", [True])
@pytest.mark.usefixtures("mock_infrared_emitter_entity", "mock_benq_to_command")
async def test_button_press_dismisses_remote_power_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """A button press dismisses the projector's power-off prompt.

    The next off press on the remote starts a new confirmation, so the media
    player stays on.
    """
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(MEDIA_PLAYER_ENTITY_ID, MediaPlayerState.ON),
                {"power_state": MediaPlayerState.ON, "source": None},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    power_off = InfraredReceivedSignal(
        timings=NECCommand(address=0x3000, command=0x4E).get_raw_timings()
    )
    mock_infrared_receiver_entity._handle_received_signal(power_off)
    await _press(hass, "button.benq_projector_menu")
    mock_infrared_receiver_entity._handle_received_signal(power_off)
    await hass.async_block_till_done()

    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.ON


@pytest.mark.parametrize("platforms", [PLATFORMS])
@pytest.mark.usefixtures("init_integration")
async def test_button_press_waits_for_power_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A button press cannot be sent between the two off commands.

    A key in between would dismiss the projector's confirmation, leaving it on.
    """
    with patch(
        "homeassistant.components.benq_projector_infrared.media_player."
        "POWER_OFF_CONFIRM_DELAY",
        0.05,
    ):
        turn_off = hass.async_create_task(
            hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                MediaPlayerService.TURN_OFF,
                {TargetKey.ENTITY_ID: MEDIA_PLAYER_ENTITY_ID},
                blocking=True,
            )
        )
        for _ in range(100):
            if mock_infrared_emitter_entity.send_command_calls:
                break
            await asyncio.sleep(0)
        assert mock_infrared_emitter_entity.send_command_calls == [
            BenQProjectorCode.POWER_OFF
        ]

        with pytest.raises(HomeAssistantError) as exc_info:
            await _press(hass, "button.benq_projector_menu")
        await turn_off

    assert exc_info.value.translation_key == "cooling_down"
    assert mock_infrared_emitter_entity.send_command_calls == [
        BenQProjectorCode.POWER_OFF,
        BenQProjectorCode.POWER_OFF,
    ]
    state = hass.states.get(MEDIA_PLAYER_ENTITY_ID)
    assert state is not None
    assert state.state == MediaPlayerState.OFF
