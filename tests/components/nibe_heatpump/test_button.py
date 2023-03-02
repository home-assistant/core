"""Test the Nibe Heat Pump config flow."""
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from nibe.coil import CoilData
from nibe.coil_groups import UNIT_COILGROUPS
from nibe.heatpump import Model
import pytest

from homeassistant.components.button import DOMAIN as PLATFORM_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import async_add_entry

from tests.common import async_fire_time_changed

MOCK_ENTRY_DATA = {
    "model": None,
    "ip_address": "127.0.0.1",
    "listening_port": 9999,
    "remote_read_port": 10000,
    "remote_write_port": 10001,
    "word_swap": True,
    "connection_type": "nibegw",
}


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.parametrize(
    ("model", "entity_id"),
    [
        (Model.F1155, "button.f1155_alarm_reset"),
        (Model.S320, "button.s320_reset_alarm"),
    ],
)
async def test_reset_button(
    hass: HomeAssistant,
    mock_connection: AsyncMock,
    model: Model,
    entity_id: str,
    coils: dict[int, Any],
    freezer: FrozenDateTimeFactory,
):
    """Test reset button."""

    unit = UNIT_COILGROUPS[model.series]["main"]

    # Setup a non alarm state
    coils[unit.alarm_reset] = 0
    coils[unit.alarm] = 0

    await async_add_entry(hass, {**MOCK_ENTRY_DATA, "model": model.name})

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # Signal alarm
    coils[unit.alarm] = 100

    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    # Press button
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify reset was written
    args = mock_connection.write_coil.call_args
    assert args
    coil: CoilData = args.args[0]
    assert coil.coil.address == unit.alarm_reset
    assert coil.value == 1
