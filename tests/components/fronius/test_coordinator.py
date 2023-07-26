"""Test the Fronius update coordinators."""
from unittest.mock import patch

from pyfronius import BadStatusError, FroniusError

from homeassistant.components.fronius.coordinator import (
    FroniusInverterUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import mock_responses, setup_fronius_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_adaptive_update_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test coordinators changing their update interval when inverter not available."""
    with patch("pyfronius.Fronius.current_inverter_data") as mock_inverter_data:
        mock_responses(aioclient_mock)
        await setup_fronius_integration(hass)
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        async_fire_time_changed(
            hass, dt_util.utcnow() + FroniusInverterUpdateCoordinator.default_interval
        )
        await hass.async_block_till_done()
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        mock_inverter_data.side_effect = FroniusError()
        # first 3 bad requests at default interval - 4th has different interval
        for _ in range(3):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + FroniusInverterUpdateCoordinator.default_interval,
            )
            await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 3
        mock_inverter_data.reset_mock()

        async_fire_time_changed(
            hass, dt_util.utcnow() + FroniusInverterUpdateCoordinator.error_interval
        )
        await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 1
        mock_inverter_data.reset_mock()

        mock_inverter_data.side_effect = None
        # next successful request resets to default interval
        async_fire_time_changed(
            hass, dt_util.utcnow() + FroniusInverterUpdateCoordinator.error_interval
        )
        await hass.async_block_till_done()
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        async_fire_time_changed(
            hass, dt_util.utcnow() + FroniusInverterUpdateCoordinator.default_interval
        )
        await hass.async_block_till_done()
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        # BadStatusError on inverter endpoints have special handling
        mock_inverter_data.side_effect = BadStatusError("mock_endpoint", 8)
        # first 3 requests at default interval - 4th has different interval
        for _ in range(3):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + FroniusInverterUpdateCoordinator.default_interval,
            )
            await hass.async_block_till_done()
        # BadStatusError does 3 silent retries for inverter endpoint * 3 request intervals = 9
        assert mock_inverter_data.call_count == 9
