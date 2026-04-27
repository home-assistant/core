"""The tests for the kitchen_sink radio frequency platform."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from rf_protocols import OOKCommand

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

ENTITY_RF_TRANSMITTER = "radio_frequency.rf_blaster_radio_frequency_transmitter"


@pytest.fixture
async def radio_frequency_only() -> None:
    """Enable only the radio_frequency platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.RADIO_FREQUENCY],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, radio_frequency_only: None) -> None:
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_send_command(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test sending a radio frequency command."""
    state = hass.states.get(ENTITY_RF_TRANSMITTER)
    assert state
    assert state.state == STATE_UNKNOWN

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)

    command = OOKCommand(frequency=433_920_000, timings=[350, -1050, 350, -350])
    await async_send_command(hass, ENTITY_RF_TRANSMITTER, command)

    state = hass.states.get(ENTITY_RF_TRANSMITTER)
    assert state
    assert state.state == now.isoformat(timespec="milliseconds")
