"""Tests of the light entity of the balboa integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pybalboa import SpaControl
from pybalboa.enums import OffOnState, UnknownState
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import client_update, init_integration

from tests.common import snapshot_platform
from tests.components.light import common

ENTITY_LIGHT = "light.fakespa_light"


@pytest.fixture(autouse=True)
def mock_light(client: MagicMock):
    """Return a mock light."""
    light = MagicMock(SpaControl)

    async def set_state(state: OffOnState):
        light.state = state

    light.name = "Light"
    light.client = client
    light.index = 0
    light.state = OffOnState.OFF
    light.set_state = set_state
    light.options = list(OffOnState)
    client.lights.append(light)

    return light


async def test_lights(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test spa light."""
    with patch("homeassistant.components.balboa.PLATFORMS", [Platform.LIGHT]):
        entry = await init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_light(hass: HomeAssistant, client: MagicMock, mock_light) -> None:
    """Test spa light."""
    await init_integration(hass)

    # check if the initial state is off
    state = hass.states.get(ENTITY_LIGHT)
    assert state.state == STATE_OFF

    # test calling turn on
    await common.async_turn_on(hass, ENTITY_LIGHT)
    state = await client_update(hass, client, ENTITY_LIGHT)
    assert state.state == STATE_ON

    # test calling turn off
    await common.async_turn_off(hass, ENTITY_LIGHT)
    state = await client_update(hass, client, ENTITY_LIGHT)
    assert state.state == STATE_OFF


async def test_light_unknown_state(
    hass: HomeAssistant, client: MagicMock, mock_light
) -> None:
    """Tests spa light with unknown state."""
    await init_integration(hass)

    mock_light.state = UnknownState.UNKNOWN
    state = await client_update(hass, client, ENTITY_LIGHT)
    assert state.state == STATE_UNKNOWN
