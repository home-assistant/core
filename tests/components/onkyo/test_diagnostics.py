"""Test Onkyo diagnostics."""

import asyncio
from datetime import timedelta

from aioonkyo import Code, Kind, Zone, status
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onkyo.coordinator import POWER_ON_QUERY_DELAY, Channel
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_receiver")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    read_queue: asyncio.Queue,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    params = dict.fromkeys(Channel, status.ChannelMuting.Param.OFF)
    params[Channel.CENTER] = status.ChannelMuting.Param.ON
    read_queue.put_nowait(
        status.ChannelMuting(
            Code.from_kind_zone(Kind.CHANNEL_MUTING, Zone.MAIN), None, **params
        )
    )
    await setup_integration(hass, mock_config_entry)

    # Let the delayed queries triggered by the initial messages run
    freezer.tick(timedelta(seconds=POWER_ON_QUERY_DELAY))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
