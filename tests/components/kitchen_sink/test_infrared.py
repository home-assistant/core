"""The tests for the kitchen_sink infrared platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import infrared_protocols
import pytest

from homeassistant.components.infrared import async_send_command
from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

ENTITY_IR_TRANSMITTER = "infrared.ir_blaster_infrared_transmitter"


@pytest.fixture
async def infrared_only() -> None:
    """Enable only the infrared platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.INFRARED],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, infrared_only: None) -> None:
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_send_command(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test sending an infrared command."""
    state = hass.states.get(ENTITY_IR_TRANSMITTER)
    assert state
    assert state.state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)

    command = infrared_protocols.NECCommand(
        address=0x04, command=0x08, modulation=38000
    )
    await async_send_command(hass, ENTITY_IR_TRANSMITTER, command)

    state = hass.states.get(ENTITY_IR_TRANSMITTER)
    assert state
    assert state.state == now.isoformat(timespec="milliseconds")
