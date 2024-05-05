"""Tests of the select entity of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from pybalboa import SpaControl
from pybalboa.enums import LowHighRange
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import client_update, init_integration

ENTITY_SELECT = "select.fakespa_temperature_range"


@pytest.fixture
def mock_select(client: MagicMock):
    """Return a mock switch."""
    select = MagicMock(SpaControl)

    async def set_state(state: LowHighRange):
        select.state = state  # mock the spacontrol state

    select.client = client
    select.state = LowHighRange.LOW
    select.set_state = set_state
    client.temperature_range = select
    return select


async def test_select(hass: HomeAssistant, client: MagicMock, mock_select) -> None:
    """Test spa temperature range select."""
    await init_integration(hass)

    # check if the initial state is off
    state = hass.states.get(ENTITY_SELECT)
    assert state.state == LowHighRange.LOW.name.lower()

    # test high state
    await _select_option_and_wait(hass, ENTITY_SELECT, LowHighRange.HIGH.name.lower())
    assert client.set_temperature_range.call_count == 1
    assert client.set_temperature_range.call_args == call(LowHighRange.HIGH)

    # test back to low state
    await _select_option_and_wait(hass, ENTITY_SELECT, LowHighRange.LOW.name.lower())
    assert client.set_temperature_range.call_count == 2  # total call count
    assert client.set_temperature_range.call_args == call(LowHighRange.LOW)


async def test_selected_option(
    hass: HomeAssistant, client: MagicMock, mock_select
) -> None:
    """Test spa temperature range selected option."""

    await init_integration(hass)

    # ensure initial low state
    state = hass.states.get(ENTITY_SELECT)
    assert state.state == LowHighRange.LOW.name.lower()

    # ensure high state
    mock_select.state = LowHighRange.HIGH
    state = await client_update(hass, client, ENTITY_SELECT)
    assert state.state == LowHighRange.HIGH.name.lower()


async def _select_option_and_wait(hass: HomeAssistant | None, entity, option):
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity,
            ATTR_OPTION: option,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
