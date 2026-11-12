"""Test the Fronius update coordinators."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from fronius_solarapi import FroniusError, StatusError
from pytest_homeassistant.common import async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.fronius.coordinator import (
    FroniusInverterUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from . import mock_responses, setup_fronius_integration


async def test_adaptive_update_interval(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinators changing their update interval when inverter not available."""
    with patch(
        "fronius_solarapi.FroniusSolarApi.inverter_common_data"
    ) as mock_inverter_data:
        mock_responses(aioclient_mock)
        await setup_fronius_integration(hass)
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        mock_inverter_data.side_effect = FroniusError()
        # first 3 bad requests at default interval - 4th has different interval
        for _ in range(3):
            freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 3
        mock_inverter_data.reset_mock()

        freezer.tick(FroniusInverterUpdateCoordinator.error_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 1
        mock_inverter_data.reset_mock()

        mock_inverter_data.side_effect = None
        # next successful request resets to default interval
        freezer.tick(FroniusInverterUpdateCoordinator.error_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_inverter_data.assert_called_once()
        mock_inverter_data.reset_mock()

        # fronius-solarapi already retried a request answered with a status
        # error, so the coordinator handles it like any other failure
        mock_inverter_data.side_effect = StatusError(
            "GetInverterRealtimeData.cgi", Mock(status=Mock(code=8, reason=""))
        )
        for _ in range(3):
            freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        assert mock_inverter_data.call_count == 3
