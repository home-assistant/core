"""Tests for the WeatherFlow Cloud coordinators."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientResponseError
import pytest
from weatherflow4py.models.ws.types import EventType
from weatherflow4py.models.ws.websocket_request import (
    ListenStartMessage,
    RapidWindListenStartMessage,
)
from weatherflow4py.models.ws.websocket_response import (
    EventDataRapidWind,
    ObservationTempestWS,
    RapidWindWS,
)

from homeassistant.components.weatherflow_cloud.coordinator import (
    WeatherFlowCloudUpdateCoordinatorREST,
    WeatherFlowObservationCoordinator,
    WeatherFlowWindCoordinator,
)
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_wind_coordinator_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_stations_data: Mock,
) -> None:
    """Test wind coordinator setup."""

    coordinator = WeatherFlowWindCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        rest_api=mock_rest_api,
        websocket_api=mock_websocket_api,
        stations=mock_stations_data,
    )

    await coordinator.async_setup()

    # Verify websocket setup
    mock_websocket_api.connect.assert_called_once()
    mock_websocket_api.register_callback.assert_called_once_with(
        message_type=EventType.RAPID_WIND,
        callback=coordinator._handle_websocket_message,
    )
    # In the refactored code, send_message is called for each device ID
    assert mock_websocket_api.send_message.called

    # Verify at least one message is of the correct type
    call_args_list = mock_websocket_api.send_message.call_args_list
    assert any(
        isinstance(call.args[0], RapidWindListenStartMessage) for call in call_args_list
    )


async def test_observation_coordinator_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_stations_data: Mock,
) -> None:
    """Test observation coordinator setup."""

    coordinator = WeatherFlowObservationCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        rest_api=mock_rest_api,
        websocket_api=mock_websocket_api,
        stations=mock_stations_data,
    )

    await coordinator.async_setup()

    # Verify websocket setup
    mock_websocket_api.connect.assert_called_once()
    mock_websocket_api.register_callback.assert_called_once_with(
        message_type=EventType.OBSERVATION,
        callback=coordinator._handle_websocket_message,
    )
    # In the refactored code, send_message is called for each device ID
    assert mock_websocket_api.send_message.called

    # Verify at least one message is of the correct type
    call_args_list = mock_websocket_api.send_message.call_args_list
    assert any(isinstance(call.args[0], ListenStartMessage) for call in call_args_list)


async def test_wind_coordinator_message_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_stations_data: Mock,
) -> None:
    """Test wind coordinator message handling."""

    coordinator = WeatherFlowWindCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        rest_api=mock_rest_api,
        websocket_api=mock_websocket_api,
        stations=mock_stations_data,
    )

    # Create mock wind data
    mock_wind_data = Mock(spec=EventDataRapidWind)
    mock_message = Mock(spec=RapidWindWS)

    # Use a device ID from the actual mock data
    # The first device from the first station in the mock data
    device_id = mock_stations_data.stations[0].devices[0].device_id
    station_id = mock_stations_data.stations[0].station_id

    mock_message.device_id = device_id
    mock_message.ob = mock_wind_data

    # Handle the message
    await coordinator._handle_websocket_message(mock_message)

    # Verify data was stored correctly
    assert coordinator._ws_data[station_id][device_id] == mock_wind_data


async def test_observation_coordinator_message_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_websocket_api: AsyncMock,
    mock_stations_data: Mock,
) -> None:
    """Test observation coordinator message handling."""

    coordinator = WeatherFlowObservationCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        rest_api=mock_rest_api,
        websocket_api=mock_websocket_api,
        stations=mock_stations_data,
    )

    # Create mock observation data
    mock_message = Mock(spec=ObservationTempestWS)

    # Use a device ID from the actual mock data
    # The first device from the first station in the mock data
    device_id = mock_stations_data.stations[0].devices[0].device_id
    station_id = mock_stations_data.stations[0].station_id

    mock_message.device_id = device_id

    # Handle the message
    await coordinator._handle_websocket_message(mock_message)

    # Verify data was stored correctly (for observations, the message IS the data)
    assert coordinator._ws_data[station_id][device_id] == mock_message


async def test_rest_coordinator_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_stations_data: Mock,
) -> None:
    """Test REST coordinator handling of 401 auth error."""
    # Create the coordinator
    coordinator = WeatherFlowCloudUpdateCoordinatorREST(
        hass=hass,
        config_entry=mock_config_entry,
        rest_api=mock_rest_api,
        stations=mock_stations_data,
    )

    # Mock a 401 auth error
    mock_rest_api.get_all_data.side_effect = ClientResponseError(
        request_info=Mock(),
        history=Mock(),
        status=401,
        message="Unauthorized",
    )

    # Verify the error is properly converted to ConfigEntryAuthFailed
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_rest_coordinator_other_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_rest_api: AsyncMock,
    mock_stations_data: Mock,
) -> None:
    """Test REST coordinator handling of non-auth errors."""
    # Create the coordinator
    coordinator = WeatherFlowCloudUpdateCoordinatorREST(
        hass=hass,
        config_entry=mock_config_entry,
        rest_api=mock_rest_api,
        stations=mock_stations_data,
    )

    # Mock a 500 server error
    mock_rest_api.get_all_data.side_effect = ClientResponseError(
        request_info=Mock(),
        history=Mock(),
        status=500,
        message="Internal Server Error",
    )

    # Verify the error is properly converted to UpdateFailed
    with pytest.raises(
        UpdateFailed, match="Update failed: 500, message='Internal Server Error'"
    ):
        await coordinator._async_update_data()
