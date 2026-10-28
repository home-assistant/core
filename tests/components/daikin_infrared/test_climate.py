"""Tests for the Daikin Infrared climate platform."""

from calendar import Day
from dataclasses import replace
from datetime import time, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.daikin_ac import (
    DaikinAcBrightness,
    DaikinAcClock,
    DaikinAcComfort,
    DaikinAcCommand,
    DaikinAcFanSpeed,
    DaikinAcMode,
    DaikinAcState,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.util import dt as dt_util

_CLIMATE_ENTITY_ID = "climate.daikin_ac"

_COOL_24 = DaikinAcState(mode=DaikinAcMode.COOL, temperature=24)


def _last_command(emitter: MockInfraredEmitterEntity) -> DaikinAcCommand:
    """Return the last command the emitter was asked to send."""
    command = emitter.send_command_calls[-1]
    assert isinstance(command, DaikinAcCommand)
    return command


def _remote(
    state: DaikinAcState, comfort: DaikinAcComfort | None = None
) -> DaikinAcCommand:
    """Return the command a physical remote sends for a state."""
    return DaikinAcCommand(
        state=state, comfort=comfort or DaikinAcComfort(), clock=DaikinAcClock()
    )


def _frames(command: DaikinAcCommand) -> list[list[int]]:
    """Split a transmission into the signals a receiver delivers, one per frame."""
    timings = command.get_raw_timings()
    frames: list[list[int]] = []
    start = 0
    for index in range(1, len(timings), 2):
        if abs(timings[index]) >= 4000:
            frames.append(timings[start : index + 1])
            start = index + 1
    return frames


def _signals(command: DaikinAcCommand, *, split: bool) -> list[list[int]]:
    """Return the signals a receiver delivers for a transmission.

    A receiver that ends a capture on a short silence delivers each frame on its own;
    one that waits out the gaps between frames delivers the whole transmission.
    """
    if split:
        return _frames(command)
    return [command.get_raw_timings()]


def _receive(receiver: MockInfraredReceiverEntity, frames: list[list[int]]) -> None:
    """Deliver each frame to the receiver as a signal of its own."""
    for frame in frames:
        receiver._handle_received_signal(InfraredReceivedSignal(timings=frame))


async def _call(hass: HomeAssistant, service: str, data: dict[str, Any]) -> None:
    """Call a climate service on the entity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, **data},
        blocking=True,
    )


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity state and registry snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("has_receiver", "source_entity_ids"),
    [
        pytest.param(False, [EMITTER_ENTITY_ID], id="emitter"),
        pytest.param(
            True, [EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID], id="emitter_and_receiver"
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_sources(
    hass: HomeAssistant, source_entity_ids: list[str]
) -> None:
    """Test the entity is available only while every infrared entity is."""
    await assert_availability_follows_source_entity(
        hass, _CLIMATE_ENTITY_ID, source_entity_ids
    )


@pytest.mark.parametrize(
    ("calls", "expected"),
    [
        pytest.param(
            [(SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})],
            _COOL_24,
            id="cool",
        ),
        pytest.param(
            [(SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT_COOL})],
            DaikinAcState(mode=DaikinAcMode.AUTO, temperature=24),
            id="heat_cool_is_auto",
        ),
        pytest.param(
            [(SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.DRY})],
            DaikinAcState(mode=DaikinAcMode.DRY, temperature=None),
            id="dry_has_no_setpoint",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF}),
            ],
            DaikinAcState(power=False, mode=DaikinAcMode.HEAT, temperature=24),
            id="off_keeps_mode",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}),
                (SERVICE_TURN_OFF, {}),
                (SERVICE_TURN_ON, {}),
            ],
            DaikinAcState(mode=DaikinAcMode.HEAT, temperature=24),
            id="turn_on_resumes_mode",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 20.4}),
            ],
            DaikinAcState(mode=DaikinAcMode.COOL, temperature=20.5),
            id="temperature_rounds_to_half_degree",
        ),
        pytest.param(
            [
                (
                    SERVICE_SET_TEMPERATURE,
                    {ATTR_TEMPERATURE: 30, ATTR_HVAC_MODE: HVACMode.HEAT},
                ),
            ],
            DaikinAcState(mode=DaikinAcMode.HEAT, temperature=30),
            id="temperature_with_mode",
        ),
        pytest.param(
            [
                (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 20}),
                (
                    SERVICE_SET_TEMPERATURE,
                    {ATTR_TEMPERATURE: 25, ATTR_HVAC_MODE: HVACMode.OFF},
                ),
            ],
            DaikinAcState(power=False, mode=DaikinAcMode.COOL, temperature=25),
            id="temperature_with_off",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 30}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}),
                (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 20}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.DRY}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
            ],
            DaikinAcState(mode=DaikinAcMode.COOL, temperature=30),
            id="each_mode_keeps_its_setpoint",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}),
                (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 10}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
            ],
            DaikinAcState(mode=DaikinAcMode.COOL, temperature=18),
            id="setpoint_clamped_to_new_mode",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "silence"}),
            ],
            DaikinAcState(
                mode=DaikinAcMode.COOL, temperature=24, fan=DaikinAcFanSpeed.SILENT
            ),
            id="fan_silence",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "3"}),
            ],
            DaikinAcState(
                mode=DaikinAcMode.COOL, temperature=24, fan=DaikinAcFanSpeed.LEVEL_3
            ),
            id="fan_level_3",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_SWING_MODE, {ATTR_SWING_MODE: "on"}),
                (SERVICE_SET_SWING_HORIZONTAL_MODE, {ATTR_SWING_HORIZONTAL_MODE: "on"}),
            ],
            DaikinAcState(
                mode=DaikinAcMode.COOL, temperature=24, swing_v=True, swing_h=True
            ),
            id="swing_both",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_ECO}),
            ],
            DaikinAcState(mode=DaikinAcMode.COOL, temperature=24, econo=True),
            id="eco",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_ECO}),
                (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_BOOST}),
            ],
            DaikinAcState(mode=DaikinAcMode.COOL, temperature=24, powerful=True),
            id="boost_clears_eco",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_ECO}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.FAN_ONLY}),
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
            ],
            DaikinAcState(mode=DaikinAcMode.COOL, temperature=24, econo=True),
            id="eco_kept_through_fan_only",
        ),
        pytest.param(
            [
                (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
                (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_BOOST}),
                (SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_NONE}),
            ],
            _COOL_24,
            id="preset_none",
        ),
    ],
)
@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_service_sends_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    calls: list[tuple[str, dict[str, Any]]],
    expected: DaikinAcState,
) -> None:
    """Test each service call sends the whole state the unit should be in."""
    for service, data in calls:
        await _call(hass, service, data)

    assert len(mock_infrared_emitter_entity.send_command_calls) == len(calls)
    assert _last_command(mock_infrared_emitter_entity).state == expected


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_command_carries_local_clock(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test every command sets the unit's clock to the local time."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-10-29 04:07:30")))
    now = dt_util.now()

    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})

    command = _last_command(mock_infrared_emitter_entity)
    assert command.clock == DaikinAcClock(
        time_of_day=now.time(), weekday=Day(now.weekday())
    )
    assert command.comfort == DaikinAcComfort()


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_target_temperature_follows_mode(hass: HomeAssistant) -> None:
    """Test the setpoint range follows the mode, and dry and fan only have none."""
    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT})
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert (state.attributes["min_temp"], state.attributes["max_temp"]) == (10, 30)
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    )

    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.FAN_ONLY})
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert ATTR_TEMPERATURE not in state.attributes
    assert not (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    )


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_boost_ends_after_twenty_minutes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test boost clears itself without sending, as the unit leaves it on its own."""
    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})
    await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_BOOST})

    freezer.tick(timedelta(minutes=19))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_BOOST

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert len(mock_infrared_emitter_entity.send_command_calls) == 2


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_boost_timer_cancelled_by_other_preset(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test leaving boost before it ends cancels its timer."""
    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})
    await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_BOOST})
    await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_ECO})

    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(SERVICE_TURN_OFF, {}, id="turn_off"),
        pytest.param(
            SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF}, id="hvac_mode_off"
        ),
    ],
)
@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_boost_ends_when_turned_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    service: str,
    data: dict[str, Any],
) -> None:
    """Test turning the unit off ends boost, as the unit leaves powerful mode."""
    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})
    await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_BOOST})
    await _call(hass, service, data)

    # The off frame goes out without powerful, as the remote sends it
    assert _last_command(mock_infrared_emitter_entity).state == replace(
        _COOL_24, power=False
    )
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # Turning back on must not bring boost back
    await _call(hass, SERVICE_TURN_ON, {})

    assert _last_command(mock_infrared_emitter_entity).state == _COOL_24


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("init_integration")
async def test_send_failure_keeps_state(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test a command the emitter fails to send leaves the state unchanged."""
    with (
        patch.object(
            mock_infrared_emitter_entity,
            "async_send_command",
            side_effect=HomeAssistantError("send failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize(
    "split",
    [
        pytest.param(True, id="one_signal_per_frame"),
        pytest.param(False, id="one_signal_per_transmission"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_receiver_updates_state(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    split: bool,
) -> None:
    """Test the physical remote's frames update the state and the next command.

    Settings the entity does not show, like the timers, are resent unchanged.
    """
    remote_state = DaikinAcState(
        mode=DaikinAcMode.HEAT,
        temperature=21,
        fan=DaikinAcFanSpeed.LEVEL_2,
        swing_h=True,
        econo=True,
        quiet=True,
        on_timer=time(6, 40),
    )
    remote_comfort = DaikinAcComfort(comfort=True, brightness=DaikinAcBrightness.DIM)

    _receive(
        mock_infrared_receiver_entity,
        _signals(_remote(remote_state, remote_comfort), split=split),
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 21
    assert state.attributes[ATTR_FAN_MODE] == "2"
    assert state.attributes[ATTR_SWING_MODE] == "off"
    assert state.attributes[ATTR_SWING_HORIZONTAL_MODE] == "on"
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    await _call(hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 22})

    command = _last_command(mock_infrared_emitter_entity)
    assert command.state == DaikinAcState(
        mode=DaikinAcMode.HEAT,
        temperature=22,
        fan=DaikinAcFanSpeed.LEVEL_2,
        swing_h=True,
        econo=True,
        quiet=True,
        on_timer=time(6, 40),
    )
    assert command.comfort == remote_comfort


@pytest.mark.usefixtures("init_integration")
async def test_receiver_applies_comfort_frame_on_its_own(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a lone comfort frame is passed on, while leaving the state alone."""
    remote_comfort = DaikinAcComfort(comfort=True)
    wake_up, comfort, clock, _ = _frames(_remote(_COOL_24, remote_comfort))
    _receive(mock_infrared_receiver_entity, [wake_up, comfort, clock, [9000, -4500]])

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF

    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})

    assert _last_command(mock_infrared_emitter_entity).comfort == remote_comfort


@pytest.mark.usefixtures("init_integration")
async def test_receiver_boost_ends_after_twenty_minutes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test powerful set on the physical remote also ends after twenty minutes."""
    _receive(
        mock_infrared_receiver_entity,
        _frames(
            _remote(
                DaikinAcState(mode=DaikinAcMode.COOL, temperature=24, powerful=True)
            )
        ),
    )
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_BOOST

    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE


_STORED = {
    "state": {
        "power": True,
        "mode": "HEAT",
        "temperature": 21.0,
        "fan": "LEVEL_4",
        "swing_v": True,
        "swing_h": False,
        "powerful": True,
        "econo": False,
        "quiet": False,
        "sensor": True,
        "on_timer": None,
        "off_timer": "22:40:00",
        "weekly_timer": False,
    },
    "comfort": {"comfort": False, "brightness": "OFF"},
    "setpoints": {"HEAT": 21.0, "COOL": 27.0},
}


@pytest.mark.parametrize("has_receiver", [False])
async def test_restore_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the whole unit state is restored, except powerful mode."""
    mock_restore_cache_with_extra_data(
        hass, [(State(_CLIMATE_ENTITY_ID, HVACMode.HEAT), _STORED)]
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 21
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    await _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL})

    command = _last_command(mock_infrared_emitter_entity)
    assert command.state == DaikinAcState(
        mode=DaikinAcMode.COOL,
        temperature=27,
        fan=DaikinAcFanSpeed.LEVEL_4,
        swing_v=True,
        sensor=True,
        off_timer=time(22, 40),
    )
    assert command.comfort == DaikinAcComfort(brightness=DaikinAcBrightness.OFF)


@pytest.mark.parametrize("has_receiver", [False])
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_restore_state_round_trip(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the state saved at shutdown is the state that was restored."""
    mock_restore_cache_with_extra_data(
        hass, [(State(_CLIMATE_ENTITY_ID, HVACMode.HEAT), _STORED)]
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await async_mock_restore_state_shutdown_restart(hass)

    (saved,) = [
        stored
        for stored in hass_storage[RESTORE_STATE_KEY]["data"]
        if stored["state"]["entity_id"] == _CLIMATE_ENTITY_ID
    ]
    # Powerful is dropped on restore, so it is saved as off
    assert saved["extra_data"] == {
        **_STORED,
        "state": {**_STORED["state"], "powerful": False},
    }


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({}, id="empty"),
        pytest.param(
            {**_STORED, "state": {**_STORED["state"], "mode": "x"}}, id="mode"
        ),
        pytest.param(
            {**_STORED, "state": {**_STORED["state"], "temperature": 40}},
            id="temperature",
        ),
    ],
)
@pytest.mark.parametrize("has_receiver", [False])
async def test_restore_invalid_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    stored: dict[str, Any],
) -> None:
    """Test stored data that is not valid is ignored."""
    mock_restore_cache_with_extra_data(
        hass, [(State(_CLIMATE_ENTITY_ID, HVACMode.HEAT), stored)]
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
