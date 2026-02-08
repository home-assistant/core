"""Test sensor of WaterFurnace integration."""

import asyncio
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from waterfurnace.waterfurnace import WFException

from homeassistant.components.waterfurnace.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_sensor(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test states of the sensor."""
    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == "1500"

    mock_waterfurnace_client.read_with_retry.return_value.totalunitpower = 2000
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wf_test_gwid_12345_totalunitpower")
    assert state
    assert state.state == "2000"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "side_effect",
    [
        WFException("Connection failed"),
        asyncio.TimeoutError,
    ],
)
async def test_availability(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    entity_id = "sensor.wf_test_gwid_12345_totalunitpower"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1500"

    mock_waterfurnace_client.read_with_retry.side_effect = side_effect
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_waterfurnace_client.read_with_retry.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "1500"
