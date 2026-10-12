"""Test Onkyo switch platform."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioonkyo import Code, Instruction, Kind, Zone, command, query, status
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.onkyo.coordinator import POWER_ON_QUERY_DELAY, Channel
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import DISCONNECT, receive_messages, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "switch.tx_nr7100_mute_front_left"


def _channel_muting_status(
    **overrides: status.ChannelMuting.Param,
) -> status.ChannelMuting:
    """Create a ChannelMuting status with all channels OFF, with overrides."""
    params = dict.fromkeys(Channel, status.ChannelMuting.Param.OFF)
    params.update(overrides)
    return status.ChannelMuting(
        Code.from_kind_zone(Kind.CHANNEL_MUTING, Zone.MAIN),
        None,
        **params,
    )


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
    read_queue.put_nowait(
        _channel_muting_status(
            front_right=status.ChannelMuting.Param.ON,
            center=status.ChannelMuting.Param.ON,
        )
    )

    with patch("homeassistant.components.onkyo.PLATFORMS", [Platform.SWITCH]):
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
    """Test NotAvailable message clears channel muting state."""
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_OFF

    await receive_messages(
        read_queue, _channel_muting_status(front_left=status.ChannelMuting.Param.ON)
    )

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_ON

    await receive_messages(
        read_queue,
        status.NotAvailable(
            Code.from_kind_zone(Kind.CHANNEL_MUTING, Zone.MAIN),
            None,
            Kind.CHANNEL_MUTING,
        ),
    )

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN


async def test_availability(hass: HomeAssistant, read_queue: asyncio.Queue) -> None:
    """Test entity availability on disconnect and reconnect."""
    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE

    await receive_messages(read_queue, DISCONNECT)

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate first status update after reconnect
    await receive_messages(
        read_queue, _channel_muting_status(front_left=status.ChannelMuting.Param.ON)
    )

    assert (state := hass.states.get(ENTITY_ID)) is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (
            SERVICE_TURN_ON,
            command.ChannelMuting(
                front_left=command.ChannelMuting.Param.ON,
                front_right=command.ChannelMuting.Param.ON,
                center=command.ChannelMuting.Param.ON,
            ),
        ),
        (
            SERVICE_TURN_OFF,
            command.ChannelMuting(
                front_right=command.ChannelMuting.Param.ON,
                center=command.ChannelMuting.Param.ON,
            ),
        ),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    writes: list[Instruction],
    action: str,
    message: Instruction,
) -> None:
    """Test actions."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert writes[0] == message


async def test_query_state_delayed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    read_queue: asyncio.Queue,
    writes: list[Instruction],
) -> None:
    """Test state query."""
    power_on = status.Power(
        Code.from_kind_zone(Kind.POWER, Zone.MAIN), None, status.Power.Param.ON
    )

    await receive_messages(read_queue, power_on)

    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Powering on again restarts the delay
    await receive_messages(read_queue, power_on)

    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.ChannelMuting)]
    assert not queries

    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY / 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    queries = [w for w in writes if isinstance(w, query.ChannelMuting)]
    assert len(queries) == 1


async def test_update_entity(
    hass: HomeAssistant,
    writes: list[Instruction],
) -> None:
    """Test manual entity update."""
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    queries = [w for w in writes if isinstance(w, query.ChannelMuting)]
    assert len(queries) == 1
