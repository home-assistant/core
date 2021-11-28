"""Test the Fronius update coordinators."""
from unittest.mock import patch

from pyfronius import FroniusError

from homeassistant.components.fronius.coordinator import (
    FroniusInverterUpdateCoordinator,
)
from homeassistant.util import dt

from . import mock_responses, setup_fronius_integration

from tests.common import async_fire_time_changed


async def test_adaptive_update_interval(hass, aioclient_mock):
    """Test coordinators changing their update interval when inverter not available."""
    with patch("pyfronius.Fronius.current_inverter_data") as mock_inverter_data:
        mock_responses(aioclient_mock)
        await setup_fronius_integration(hass)
        assert mock_inverter_data.call_count == 1

        async_fire_time_changed(
            hass, dt.utcnow() + FroniusInverterUpdateCoordinator.default_interval
        )
        await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 2

        mock_inverter_data.side_effect = FroniusError
        # first 3 requests at default interval - 4th has different interval
        for _ in range(4):
            async_fire_time_changed(
                hass, dt.utcnow() + FroniusInverterUpdateCoordinator.default_interval
            )
            await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 5
        async_fire_time_changed(
            hass, dt.utcnow() + FroniusInverterUpdateCoordinator.error_interval
        )
        await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 6

        mock_inverter_data.side_effect = None
        # next successful request resets to default interval
        async_fire_time_changed(
            hass, dt.utcnow() + FroniusInverterUpdateCoordinator.error_interval
        )
        await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 7

        async_fire_time_changed(
            hass, dt.utcnow() + FroniusInverterUpdateCoordinator.default_interval
        )
        await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 8
