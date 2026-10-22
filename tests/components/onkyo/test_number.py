"""Test Onkyo number platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioonkyo import Code, Instruction, Kind, Zone, command, query, status
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.onkyo.coordinator import POWER_ON_QUERY_DELAY
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import DISCONNECT, receive_messages, setup_integration

BASS_ENTITY_ID = "number.tx_nr7100_bass"
TREBLE_ENTITY_ID = "number.tx_nr7100_treble"


def _tone_status(bass: int, treble: int) -> status.Tone:
    """Create a Tone status of the main zone."""
    return status.Tone(Code.from_kind_zone(Kind.TONE, Zone.MAIN), None, bass, treble)


def _power_status(param: status.Power.Param) -> status.Power:
    """Create a Power status of the main zone."""
    return status.Power(Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, param)


@pytest.fixture(autouse=True)
async def auto_setup_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_receiver: AsyncMock,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> AsyncGenerator[None]:
    """Auto setup integration."""
    read_queue.put_nowait(_tone_status(-3, 2))

    with patch("homeassistant.components.onkyo.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

        # Let the delayed queries triggered by the initial messages run
        freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        writes.clear()
        yield


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state_changes(hass: HomeAssistant, read_queue: asyncio.Queue) -> None:
    """Test tone status updates and NotAvailable."""
    await receive_messages(read_queue, _tone_status(4, -6))

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == "4"
    assert (state := hass.states.get(TREBLE_ENTITY_ID)) is not None
    assert state.state == "-6"

    # Not available, e.g. in a listening mode without tone controls
    await receive_messages(
        read_queue,
        status.NotAvailable(Code.from_kind_zone(Kind.TONE, Zone.MAIN), None, Kind.TONE),
    )

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_availability(hass: HomeAssistant, read_queue: asyncio.Queue) -> None:
    """Test entity availability on standby, disconnect and reconnect."""
    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == "-3"

    # The receiver ignores tone commands in standby
    await receive_messages(read_queue, _power_status(status.Power.Param.STANDBY))

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    await receive_messages(read_queue, _power_status(status.Power.Param.ON))

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == "-3"

    await receive_messages(read_queue, DISCONNECT)

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate the first status updates after reconnect
    await receive_messages(
        read_queue, _power_status(status.Power.Param.ON), _tone_status(-3, 2)
    )

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == "-3"


@pytest.mark.parametrize(
    ("entity_id", "value", "message"),
    [
        (BASS_ENTITY_ID, 5, command.Tone(zone=Zone.MAIN, bass=5)),
        (TREBLE_ENTITY_ID, -10, command.Tone(zone=Zone.MAIN, treble=-10)),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    writes: list[Instruction],
    entity_id: str,
    value: int,
    message: Instruction,
) -> None:
    """Test actions."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    assert writes == [message]


async def test_query_state_delayed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test state query after power on."""
    await receive_messages(read_queue, _power_status(status.Power.Param.ON))

    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Powering on again restarts the delay
    await receive_messages(read_queue, _power_status(status.Power.Param.ON))

    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.Tone)]
    assert not queries

    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.Tone)]
    assert queries == [query.Tone(Zone.MAIN)]


async def test_update_entity(
    hass: HomeAssistant,
    writes: list[Instruction],
) -> None:
    """Test manual entity update."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: BASS_ENTITY_ID},
        blocking=True,
    )

    queries = [w for w in writes if isinstance(w, query.Tone)]
    assert len(queries) == 1


async def test_update_entity_failed(
    hass: HomeAssistant,
    mock_receiver: AsyncMock,
    read_queue: asyncio.Queue,
) -> None:
    """Test entities are unavailable after a failed manual update."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    mock_receiver.write = AsyncMock(side_effect=OSError)

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: BASS_ENTITY_ID},
        blocking=True,
    )

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    await receive_messages(read_queue, _tone_status(-3, 2))

    assert (state := hass.states.get(BASS_ENTITY_ID)) is not None
    assert state.state == "-3"
