"""Tests for the Gree Infrared switch platform."""

import asyncio
from unittest.mock import patch

from infrared_protocols.commands.gree_ac import (
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.gree_infrared.const import DOMAIN
from homeassistant.components.infrared import InfraredCommand, InfraredReceivedSignal
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_TURBO_ENTITY_ID = "switch.gree_ac_turbo"
_LIGHT_ENTITY_ID = "switch.gree_ac_panel_light"
_XFAN_ENTITY_ID = "switch.gree_ac_xtra_fan"
_CLIMATE_ENTITY_ID = "climate.gree_ac"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.SWITCH]


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return False


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity state and registry snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration", "mock_infrared_emitter_entity")
@pytest.mark.parametrize(
    "entity_id", [_TURBO_ENTITY_ID, _LIGHT_ENTITY_ID, _XFAN_ENTITY_ID]
)
async def test_availability_follows_emitter(
    hass: HomeAssistant,
    entity_id: str,
) -> None:
    """Test switch availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(hass, entity_id, EMITTER_ENTITY_ID)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "on_command", "off_command"),
    [
        pytest.param(
            _TURBO_ENTITY_ID,
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=True,
                display=True,
                blow=False,
            ),
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=False,
                display=True,
                blow=False,
            ),
            id="turbo",
        ),
        pytest.param(
            _LIGHT_ENTITY_ID,
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=False,
                display=True,
                blow=False,
            ),
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=False,
                display=False,
                blow=False,
            ),
            id="light",
        ),
        pytest.param(
            _XFAN_ENTITY_ID,
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=False,
                display=True,
                blow=True,
            ),
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=False,
                display=True,
                blow=False,
            ),
            id="xfan",
        ),
    ],
)
async def test_switch_encodes_both_states(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    on_command: GreeAcCommand,
    off_command: GreeAcCommand,
) -> None:
    """Test each switch sends a whole frame carrying its own flag, on and off."""
    for service, expected_command, expected_state in (
        (SERVICE_TURN_ON, on_command, STATE_ON),
        (SERVICE_TURN_OFF, off_command, STATE_OFF),
    ):
        mock_infrared_emitter_entity.send_command_calls.clear()

        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        assert len(mock_infrared_emitter_entity.send_command_calls) == 1
        timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
        assert timings == expected_command.get_raw_timings()

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.usefixtures("init_integration")
async def test_switch_frame_carries_the_climate_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a switch resends the mode, temperature and fan the climate entity set.

    Every frame carries the whole state, so a switch that sent only its own flag
    would reset the unit to the protocol defaults.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_MEDIUM},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _TURBO_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.DRY,
            temperature=25,
            fan=GreeAcFanSpeed.MEDIUM,
            turbo=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.usefixtures("init_integration")
async def test_switch_frame_carries_changes_made_while_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a switch resends the temperature and fan set while the unit is off.

    Neither change sends a frame of its own, but both are what the climate entity
    shows, so a frame going out for another reason has to carry them.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 27},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_MEDIUM},
        blocking=True,
    )
    assert not mock_infrared_emitter_entity.send_command_calls

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _XFAN_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.COOL,
            temperature=27,
            fan=GreeAcFanSpeed.MEDIUM,
            blow=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
async def test_switch_frame_carries_a_remote_frame_with_climate_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    platforms: list[Platform],
) -> None:
    """Test the switches keep up with the remote while the climate entity is disabled.

    A disabled entity is never added, so the frame it would have recorded has to be
    recorded for the entry rather than by it. Otherwise the next switch toggle sends
    the defaults back and turns the unit off.
    """
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        CLIMATE_DOMAIN,
        DOMAIN,
        mock_config_entry.entry_id,
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(_CLIMATE_ENTITY_ID) is None

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.COOL,
                temperature=27,
                fan=GreeAcFanSpeed.HIGH,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _XFAN_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL,
            temperature=27,
            fan=GreeAcFanSpeed.HIGH,
            blow=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.usefixtures("init_integration")
async def test_climate_frame_carries_the_switch_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the climate entity keeps the flags the switches turned on."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _XFAN_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY_ID},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
            display=False,
            blow=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.usefixtures("init_integration")
async def test_overlapping_sends_keep_both_changes(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a switch and the climate entity sending at once keep both changes.

    The platforms have a PARALLEL_UPDATES semaphore each, so their service calls
    overlap; both would otherwise build a frame from the same snapshot and the
    unit would obey whichever frame arrived last.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    sending = asyncio.Event()
    finish_sending = asyncio.Event()
    send_command = mock_infrared_emitter_entity.async_send_command

    async def blocking_send(command: InfraredCommand) -> None:
        """Hold the first frame in flight until the second call has been made."""
        if not sending.is_set():
            sending.set()
            await finish_sending.wait()
        await send_command(command)

    with patch.object(
        mock_infrared_emitter_entity, "async_send_command", blocking_send
    ):
        turbo_call = hass.async_create_task(
            hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: _TURBO_ENTITY_ID},
                blocking=True,
            )
        )
        await sending.wait()
        temperature_call = hass.async_create_task(
            hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
                blocking=True,
            )
        )
        for _ in range(5):
            await asyncio.sleep(0)
        finish_sending.set()
        await turbo_call
        await temperature_call

    assert len(mock_infrared_emitter_entity.send_command_calls) == 2
    timings = mock_infrared_emitter_entity.send_command_calls[1].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL,
            temperature=25,
            fan=GreeAcFanSpeed.AUTO,
            turbo=True,
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_failed_send_leaves_the_flag_unset(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a flag whose frame never went out is not carried by the next frame.

    The unit only has the feature on if its frame was actually transmitted, so a
    send that raised must leave both the switch and the shared state alone.
    """
    with (
        patch.object(
            mock_infrared_emitter_entity,
            "async_send_command",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: _TURBO_ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(_TURBO_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _XFAN_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.COOL,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
            turbo=False,
            blow=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize(
    ("restored_state", "expected_state", "expected_command"),
    [
        pytest.param(
            STATE_ON,
            STATE_ON,
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=True,
                blow=True,
            ),
            id="restored_on",
        ),
        pytest.param(
            STATE_UNAVAILABLE,
            STATE_OFF,
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
                turbo=False,
                blow=True,
            ),
            id="unavailable_falls_back_to_off",
        ),
    ],
)
async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_state: str,
    expected_state: str,
    expected_command: GreeAcCommand,
) -> None:
    """Test the assumed state is restored and reaches the next frame sent."""
    mock_restore_cache(hass, [State(_TURBO_ENTITY_ID, restored_state)])
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_TURBO_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state

    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _XFAN_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_command.get_raw_timings()


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_updates_state(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a physical remote frame updates every switch it carries a flag for."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.COOL,
                temperature=24,
                fan=GreeAcFanSpeed.AUTO,
                turbo=True,
                display=False,
                blow=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    for entity_id, expected_state in (
        (_TURBO_ENTITY_ID, STATE_ON),
        (_LIGHT_ENTITY_ID, STATE_OFF),
        (_XFAN_ENTITY_ID, STATE_ON),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.usefixtures("init_integration")
async def test_next_frame_keeps_the_louvres_the_remote_set(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a swing position seen on the receiver survives the next frame sent.

    No entity exposes the louvres, so the only way they reach a frame HA sends is
    by being carried through from the one the physical remote sent.
    """
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.COOL,
                temperature=24,
                fan=GreeAcFanSpeed.AUTO,
                swing_v=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _TURBO_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL,
            temperature=24,
            fan=GreeAcFanSpeed.AUTO,
            swing_v=True,
            turbo=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.usefixtures("init_integration")
async def test_unconfigured_mode_frame_reaches_neither_entity(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a frame in an unconfigured mode is dropped whole, flags included.

    A mode the user did not configure is another unit's, so recording its flags
    would leave the shared state mixing that frame with the mode, temperature and
    fan of the one before it.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.HEAT,
                temperature=24,
                fan=GreeAcFanSpeed.HIGH,
                turbo=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    mock_infrared_emitter_entity.send_command_calls.clear()

    state = hass.states.get(_TURBO_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY_ID},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
            display=False,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_non_gree_ac_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that an unrecognised IR signal does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[500, -500, 300, -300])
    )
    await hass.async_block_till_done()

    state = hass.states.get(_TURBO_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
