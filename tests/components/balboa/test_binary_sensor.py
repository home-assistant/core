"""Tests of the climate entity of the balboa integration."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_BINARY_SENSOR = "binary_sensor.fakespa_"


async def test_filters(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test spa filters."""
    for num in (1, 2):
        sensor = f"{ENTITY_BINARY_SENSOR}filter{num}"

        state = hass.states.get(sensor)
        assert state.state == STATE_OFF

        setattr(client, f"filter_cycle_{num}_running", True)
        client.emit("")
        await hass.async_block_till_done()

        state = hass.states.get(sensor)
        assert state.state == STATE_ON


async def test_circ_pump(
    hass: HomeAssistant, client: MagicMock, integration: MockConfigEntry
) -> None:
    """Test spa circ pump."""
    sensor = f"{ENTITY_BINARY_SENSOR}circ_pump"

    state = hass.states.get(sensor)
    assert state.state == STATE_OFF

    client.circulation_pump.state = 1
    client.emit("")
    await hass.async_block_till_done()

    state = hass.states.get(sensor)
    assert state.state == STATE_ON
