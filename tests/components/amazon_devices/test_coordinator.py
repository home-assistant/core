"""Tests for the Amazon Devices coordinator."""

from unittest.mock import AsyncMock

from aioamazondevices.exceptions import (
    CannotAuthenticate,
    CannotConnect,
    CannotRetrieveData,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.amazon_devices.const import SCAN_INTERVAL
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "side_effect",
    [
        CannotConnect,
        CannotRetrieveData,
        CannotAuthenticate,
    ],
)
async def test_coordinator_data_update_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test coordinator data update exceptions."""

    entity_id = "binary_sensor.echo_test_connectivity"

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    mock_amazon_devices_client.get_devices_data.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE
