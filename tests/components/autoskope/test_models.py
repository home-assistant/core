"""Test Autoskope models."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.autoskope.const import (
    APP_VERSION,
    DEFAULT_MODEL,
    DEVICE_TYPE_MODELS,
)
from homeassistant.components.autoskope.models import (
    AutoskopeApi,
    CannotConnect,
    InvalidAuth,
    PositionDataApi,
    Vehicle,
    VehicleInfoApi,
    VehiclePosition,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


def test_vehicle_position_from_geojson() -> None:
    """Test creating VehiclePosition from GeoJSON."""
    # Test valid data
    feature: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0484209, 54.3166084]},
        "properties": {
            "carid": "123",
            "s": "5.0",
            "park": 0,
            "dt": "2023-01-01 12:00:00",
        },
    }
    position = VehiclePosition.from_geojson(feature)
    assert position is not None
    assert position.latitude == 54.3166084
    assert position.longitude == 13.0484209
    assert position.speed == 5.0
    assert position.timestamp == "2023-01-01 12:00:00"
    assert not position.park_mode

    # Test parked car with boolean park mode
    feature_parked_bool: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0484209, 54.3166084]},
        "properties": {
            "carid": "123",
            "s": "0.0",
            "park": True,
            "dt": "2023-01-01 12:00:00",
        },
    }
    position_parked_bool = VehiclePosition.from_geojson(feature_parked_bool)
    assert position_parked_bool is not None
    assert position_parked_bool.park_mode is True

    # Test parked car with integer park mode
    feature_parked_int: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0484209, 54.3166084]},
        "properties": {
            "carid": "123",
            "s": "0.0",
            "park": 1,
            "dt": "2023-01-01 12:00:00",
        },
    }
    position_parked_int = VehiclePosition.from_geojson(feature_parked_int)
    assert position_parked_int is not None
    assert position_parked_int.park_mode is True

    # Test invalid data structure
    invalid_feature: Any = {"geometry": {"invalid": "data"}}
    assert VehiclePosition.from_geojson(invalid_feature) is None

    # Test missing geometry key
    missing_geometry: Any = {"type": "Feature", "properties": {"carid": "123"}}
    assert VehiclePosition.from_geojson(missing_geometry) is None

    # Test invalid coordinates length
    invalid_coords: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0]},
        "properties": {"dt": "2023-01-01 12:00:00"},
    }
    assert VehiclePosition.from_geojson(invalid_coords) is None


def test_vehicle_position_from_geojson_invalid_types() -> None:
    """Test VehiclePosition.from_geojson with invalid property types."""
    # Test invalid speed
    feature_invalid_speed: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0, 54.0]},
        "properties": {"s": "not-a-float", "park": 0, "dt": "2023-01-01 12:00:00"},
    }
    position = VehiclePosition.from_geojson(feature_invalid_speed)
    assert position is not None
    assert position.speed == 0.0  # Should default to 0.0 on ValueError

    # Test invalid park
    feature_invalid_park: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0, 54.0]},
        "properties": {"s": "5.0", "park": "not-an-int", "dt": "2023-01-01 12:00:00"},
    }
    position = VehiclePosition.from_geojson(feature_invalid_park)
    assert position is not None
    assert (
        position.park_mode is False
    )  # Should default to False on ValueError/TypeError

    # Test missing dt
    feature_missing_dt: Any = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [13.0, 54.0]},
        "properties": {"s": "5.0", "park": 0},
    }
    position = VehiclePosition.from_geojson(feature_missing_dt)
    assert position is None


def test_vehicle_from_api() -> None:
    """Test creating Vehicle from API response."""
    # Test with position data
    vehicle_info: VehicleInfoApi = {
        "id": "123",
        "name": "Test Vehicle",
        "ex_pow": "12.5",
        "bat_pow": "4.1",
        "hdop": "1.0",
        "support_infos": {"imei": "123456789012345"},
        "device_type_id": "1",
    }

    position_data: PositionDataApi = {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [13.0484209, 54.3166084]},
                "properties": {
                    "carid": "123",
                    "s": "0",
                    "park": 1,
                    "dt": "2023-01-01 12:00:00",
                },
            }
        ]
    }

    vehicle = Vehicle.from_api(vehicle_info, position_data)
    assert vehicle.id == "123"
    assert vehicle.name == "Test Vehicle"
    assert vehicle.external_voltage == 12.5
    assert vehicle.battery_voltage == 4.1
    assert vehicle.gps_quality == 1.0
    assert vehicle.imei == "123456789012345"
    assert vehicle.model == DEVICE_TYPE_MODELS.get("1", DEFAULT_MODEL)

    # Test without position data
    vehicle_without_position = Vehicle.from_api(vehicle_info, None)
    assert vehicle_without_position.position is None

    # Test with unknown device type ID
    vehicle_info["device_type_id"] = "999"
    vehicle_unknown_type = Vehicle.from_api(vehicle_info, None)
    assert vehicle_unknown_type.model == DEFAULT_MODEL

    # Test with missing support_infos
    vehicle_info_no_support: VehicleInfoApi = {
        "id": "456",
        "name": "No Support Info",
        "ex_pow": "12.0",
        "bat_pow": "4.0",
        "hdop": "1.1",
        "support_infos": None,
        "device_type_id": "2",
    }
    vehicle_no_support_info = Vehicle.from_api(vehicle_info_no_support, None)
    assert vehicle_no_support_info.imei is None
    assert vehicle_no_support_info.model == DEVICE_TYPE_MODELS.get("2", DEFAULT_MODEL)


def test_vehicle_from_api_missing_data(snapshot: SnapshotAssertion) -> None:
    """Test Vehicle.from_api with missing required data."""
    # Missing required fields like ex_pow, bat_pow, hdop
    data_info_missing_req: VehicleInfoApi = {
        "id": "v1",
        "name": "Test Vehicle 1",
        "support_infos": None,
        "device_type_id": None,
    }
    data_status: PositionDataApi = {"features": []}
    with pytest.raises(ValueError, match="Invalid vehicle data structure: 'ex_pow'"):
        Vehicle.from_api(data_info_missing_req, data_status)

    # Test with keys present but None
    data_info_none_vals: VehicleInfoApi = {
        "id": "v1_none",
        "name": "Test Vehicle None",
        "ex_pow": None,
        "bat_pow": None,
        "hdop": None,
        "support_infos": None,
        "device_type_id": None,
    }
    with pytest.raises(ValueError, match="Invalid vehicle data structure: float"):
        Vehicle.from_api(data_info_none_vals, data_status)

    # Missing features key in status
    data_info_complete: VehicleInfoApi = {
        "id": "v1_complete",
        "name": "Test Vehicle Complete",
        "ex_pow": "12.1",
        "bat_pow": "4.0",
        "hdop": "1.1",
        "support_infos": {"imei": "I1"},
        "device_type_id": "1",
    }
    data_status_no_features: PositionDataApi = {}
    vehicle_no_features = Vehicle.from_api(data_info_complete, data_status_no_features)
    assert vehicle_no_features.position is None
    assert vehicle_no_features == snapshot

    # Missing optional fields in info
    data_info_minimal: VehicleInfoApi = {
        "id": "v2",
        "name": "Minimal Vehicle",
        "ex_pow": "12.2",
        "bat_pow": "4.2",
        "hdop": "1.2",
        "support_infos": None,
        "device_type_id": None,
    }
    vehicle_minimal_info = Vehicle.from_api(data_info_minimal, data_status)
    assert vehicle_minimal_info.imei is None
    assert vehicle_minimal_info.model == DEFAULT_MODEL
    assert vehicle_minimal_info.position is None
    assert vehicle_minimal_info == snapshot

    # Empty info dict
    with pytest.raises(ValueError, match="Invalid vehicle data structure: 'id'"):
        Vehicle.from_api({}, {})


def test_vehicle_from_api_invalid_types(snapshot: SnapshotAssertion) -> None:
    """Test Vehicle.from_api with invalid data types for required fields."""
    # Invalid types for voltages, gps_quality
    data_info_invalid_nums: VehicleInfoApi = {
        "id": "v_inv",
        "name": "Invalid Type",
        "ex_pow": "invalid",
        "bat_pow": [4, 0],
        "hdop": {"quality": 1.0},
        "support_infos": {"imei": "I_INV"},
        "device_type_id": "1",
    }
    data_status: PositionDataApi = {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {
                    "carid": "v_inv",
                    "s": "0.0",
                    "park": True,
                    "dt": "2023-01-01T00:00:00Z",
                },
            }
        ]
    }
    with pytest.raises(
        ValueError,
        match="Invalid vehicle data structure: could not convert string to float: 'invalid'",
    ):
        Vehicle.from_api(data_info_invalid_nums, data_status)

    # Test with valid numeric types but invalid position data structure
    data_info_valid_nums: VehicleInfoApi = {
        "id": "v_inv_pos",
        "name": "Inv Pos",
        "ex_pow": "12.3",
        "bat_pow": "4.3",
        "hdop": "1.3",
        "support_infos": {"imei": "I_INV_POS"},
        "device_type_id": "1",
    }
    data_status_invalid_pos: PositionDataApi = {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0]},
                "properties": {"latitude": "bad"},
            }
        ]
    }
    vehicle_invalid_pos = Vehicle.from_api(
        data_info_valid_nums, data_status_invalid_pos
    )
    assert vehicle_invalid_pos.position is None
    assert vehicle_invalid_pos == snapshot


def test_vehicle_from_api_position_edge_cases(snapshot: SnapshotAssertion) -> None:
    """Test Vehicle.from_api position handling edge cases."""
    # Use valid info data
    data_info: VehicleInfoApi = {
        "id": "v_pos_edge",
        "name": "Position Edge Case",
        "ex_pow": "12.5",
        "bat_pow": "4.5",
        "hdop": "1.5",
        "support_infos": {"imei": "I_EDGE"},
        "device_type_id": "1",
    }

    # Case 1: position_data is not None, but 'features' key is missing
    data_status_no_features_key: PositionDataApi = {}
    vehicle = Vehicle.from_api(data_info, data_status_no_features_key)
    assert vehicle.position is None
    assert vehicle == snapshot

    # Case 2: 'features' is present but empty list
    data_status_empty_features: PositionDataApi = {"features": []}
    vehicle = Vehicle.from_api(data_info, data_status_empty_features)
    assert vehicle.position is None
    assert vehicle == snapshot

    # Case 3: 'features' has items, but none match carid
    data_status_wrong_carid: PositionDataApi = {
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {"carid": "wrong_id", "dt": "ts"},
            }
        ]
    }
    vehicle = Vehicle.from_api(data_info, data_status_wrong_carid)
    assert vehicle.position is None
    assert vehicle == snapshot

    # Case 4: 'features' contains various invalid structures
    data_status_invalid_geojson: PositionDataApi = {
        "features": [
            None,
            "not a dict",
            {"type": "Feature", "properties": None},
            {"type": "Feature", "geometry": None},
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": ["list"],
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {"carid": "other_id", "dt": "ts1"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
                "properties": {"carid": "v_pos_edge", "s": "5"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
                "properties": {
                    "carid": "v_pos_edge",
                    "s": "10",
                    "park": 0,
                    "dt": "2023-01-01T00:00:00Z",
                },
            },
        ]
    }
    vehicle = Vehicle.from_api(data_info, data_status_invalid_geojson)
    assert vehicle.position is not None
    assert vehicle.position.latitude == 2.0
    assert vehicle == snapshot


@pytest.fixture
def mock_hass() -> MagicMock:
    """Fixture for a mock HomeAssistant object."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}
    hass.loop = asyncio.get_event_loop()
    hass.bus = MagicMock()
    hass.bus.async_listen_once = MagicMock()
    return hass


@pytest.fixture
def api(mock_hass: MagicMock) -> AutoskopeApi:
    """Fixture for an AutoskopeApi instance."""
    return AutoskopeApi(
        "https://mock.autoskope.api", "test-user", "test-pass", mock_hass
    )


@pytest.fixture
def mock_client_response():
    """Create a mock aiohttp client response context manager."""
    response_mock = MagicMock(spec=aiohttp.ClientResponse)
    response_mock.status = 200
    response_mock.headers = {}
    response_mock.text = AsyncMock(return_value="")
    response_mock.__aenter__ = AsyncMock(return_value=response_mock)
    response_mock.__aexit__ = AsyncMock(return_value=None)
    return response_mock


async def test_autoskope_api_init(mock_hass: MagicMock) -> None:
    """Test initialization of AutoskopeApi."""
    api_instance = AutoskopeApi(
        "https://example.com/", "username", "password", mock_hass
    )
    assert api_instance._host == "https://example.com"
    assert api_instance._username == "username"
    assert api_instance._password == "password"
    assert api_instance._hass is mock_hass


async def test_autoskope_api_get_session(mock_hass: MagicMock) -> None:
    """Test getting a session."""
    api_instance = AutoskopeApi(
        "https://example.com", "username", "password", mock_hass
    )

    mock_session = MagicMock(spec=aiohttp.ClientSession)

    with patch(
        "homeassistant.components.autoskope.models.async_get_clientsession",
        return_value=mock_session,
    ) as mock_get_session:
        session1 = await api_instance._get_session()
        assert session1 is mock_session
        mock_get_session.assert_called_once_with(mock_hass)

        mock_get_session.reset_mock()
        session2 = await api_instance._get_session()
        assert session2 is mock_session
        mock_get_session.assert_called_once_with(mock_hass)


async def test_autoskope_api_authenticate_success(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test successful authentication with Autoskope API."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.text = AsyncMock(return_value="")
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    with patch.object(api, "_get_session", return_value=mock_session):
        result = await api.authenticate()
        assert result is True
        mock_session.request.assert_called_once_with(
            "post",
            f"{api._host}/scripts/ajax/login.php",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "username": api._username,
                "password": api._password,
                "appversion": APP_VERSION,
            },
            timeout=10,
        )


async def test_autoskope_api_authenticate_failure(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test failed authentication with Autoskope API."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response

    with patch.object(api, "_get_session", return_value=mock_session):
        mock_client_response.status = 401
        mock_client_response.text = AsyncMock(return_value="Auth error")
        with pytest.raises(InvalidAuth, match="Authentication failed"):
            await api.authenticate()

        mock_client_response.status = 200
        mock_client_response.text = AsyncMock(return_value="Error message")
        with pytest.raises(InvalidAuth, match="Authentication failed"):
            await api.authenticate()

        mock_session.request.side_effect = aiohttp.ClientError("Connection failed")
        with pytest.raises(
            CannotConnect, match="Connection error during authentication"
        ):
            await api.authenticate()
        mock_session.request.side_effect = None

        mock_session.request.side_effect = Exception("Generic issue")
        with pytest.raises(
            CannotConnect, match="Connection error during authentication"
        ):
            await api.authenticate()


async def test_autoskope_api_get_vehicles_success(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test getting vehicles successfully."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    response_data = {
        "cars": [
            {
                "id": "123",
                "name": "Test Vehicle",
                "ex_pow": "12.5",
                "bat_pow": "4.1",
                "hdop": "1.0",
                "device_type_id": "1",
                "support_infos": {"imei": "IMEI123"},
            }
        ],
        "lastPos": json.dumps(
            {
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [13.0484209, 54.3166084],
                        },
                        "properties": {
                            "carid": "123",
                            "s": "0",
                            "park": 1,
                            "dt": "2023-01-01 12:00:00",
                        },
                    }
                ]
            }
        ),
    }
    mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

    with patch.object(api, "_get_session", return_value=mock_session):
        vehicles = await api.get_vehicles()
        assert len(vehicles) == 1
        assert vehicles[0].id == "123"
        assert vehicles[0].name == "Test Vehicle"
        assert vehicles[0].position is not None
        mock_session.request.assert_called_once_with(
            "post",
            f"{api._host}/scripts/ajax/app/info.php",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"appversion": APP_VERSION},
            timeout=20,
        )


async def test_autoskope_api_get_vehicles_auth_failure(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test getting vehicles with authentication failure (e.g., 401 from API)."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 401
    mock_client_response.headers = {}
    mock_client_response.text = AsyncMock(return_value="Auth Error Text")

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(UpdateFailed, match="Authentication required"),
    ):
        await api.get_vehicles()


async def test_autoskope_api_get_vehicles_api_error(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test getting vehicles with API connection or server error."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    with patch.object(api, "_get_session", return_value=mock_session):
        mock_session.request.side_effect = aiohttp.ClientError("Connection failed")
        with pytest.raises(
            UpdateFailed,
            match="Failed to fetch data from Autoskope API: Error connecting to Autoskope API: Connection failed",
        ):
            await api.get_vehicles()
        mock_session.request.side_effect = None

        mock_session.request.return_value = mock_client_response
        mock_client_response.status = 500
        mock_client_response.headers = {}
        mock_client_response.text = AsyncMock(return_value="Server Error Text")
        with pytest.raises(
            UpdateFailed,
            match="Failed to fetch data from Autoskope API: API request failed with status 500",
        ):
            await api.get_vehicles()


async def test_autoskope_api_get_vehicles_json_error(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test getting vehicles with JSON parsing error in response."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    with patch.object(api, "_get_session", return_value=mock_session):
        mock_client_response.text = AsyncMock(return_value="Invalid JSON {")
        with pytest.raises(
            UpdateFailed,
            match="Failed to fetch data from Autoskope API: Received invalid response from API",
        ):
            await api.get_vehicles()

        mock_client_response.text = AsyncMock(return_value='["list", "not", "dict"]')
        with pytest.raises(
            UpdateFailed,
            match="Failed to fetch data from Autoskope API: Received non-dictionary JSON response from API",
        ):
            await api.get_vehicles()

        mock_client_response.text = AsyncMock(
            return_value='{"no_cars_key": true, "lastPos": "{}"}'
        )
        assert await api.get_vehicles() == []


async def test_autoskope_api_get_vehicles_login_page(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test get_vehicles receiving login page (triggers InvalidAuth -> UpdateFailed)."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}
    mock_client_response.text = AsyncMock(
        return_value="<title>Login</title>Some HTML login.php"
    )

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(UpdateFailed, match="Authentication required"),
    ):
        await api.get_vehicles()


async def test_autoskope_api_get_vehicles_invalid_lastpos_json(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test get_vehicles with lastPos being invalid JSON."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    response_data = {
        "cars": [
            {
                "id": "123",
                "name": "Test Vehicle",
                "ex_pow": "12.5",
                "bat_pow": "4.1",
                "hdop": "1.0",
                "device_type_id": "1",
                "support_infos": {"imei": "IMEI123"},
            }
        ],
        "lastPos": "{invalid json string",
    }
    mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

    with patch.object(api, "_get_session", return_value=mock_session):
        vehicles = await api.get_vehicles()
        assert len(vehicles) == 1
        assert vehicles[0].id == "123"
        assert vehicles[0].position is None


async def test_autoskope_api_get_vehicles_cars_not_list(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test get_vehicles when 'cars' key is not a list."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    response_data = {
        "cars": {"not": "a list"},
        "lastPos": "{}",
    }
    mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(
            UpdateFailed, match="Invalid vehicle data format in API response"
        ),
    ):
        await api.get_vehicles()


async def test_autoskope_api_get_vehicles_car_item_not_dict(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test get_vehicles when an item in 'cars' list is not a dict."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    response_data = {
        "cars": [
            123,
            {
                "id": "valid_car",
                "name": "Valid Car",
                "ex_pow": "12.0",
                "bat_pow": "4.0",
                "hdop": "1.0",
                "device_type_id": "1",
                "support_infos": {"imei": "IMEI_VALID"},
            },
        ],
        "lastPos": "{}",
    }
    mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

    with patch.object(api, "_get_session", return_value=mock_session):
        vehicles = await api.get_vehicles()
        assert len(vehicles) == 1
        assert vehicles[0].id == "valid_car"


async def test_autoskope_api_get_vehicles_lastpos_not_string(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test get_vehicles with lastPos being present but not a string."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    response_data = {
        "cars": [
            {
                "id": "123",
                "name": "Test Vehicle",
                "ex_pow": "12.5",
                "bat_pow": "4.1",
                "hdop": "1.0",
                "device_type_id": "1",
                "support_infos": {"imei": "IMEI123"},
            }
        ],
        "lastPos": 12345,
    }
    mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

    with patch.object(api, "_get_session", return_value=mock_session):
        vehicles = await api.get_vehicles()
        assert len(vehicles) == 1
        assert vehicles[0].id == "123"
        assert vehicles[0].position is None


async def test_autoskope_api_get_vehicles_unexpected_error(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test get_vehicles handling unexpected error during processing."""
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/html"}

    response_data = {"cars": [], "lastPos": "{}"}
    mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        patch(
            "homeassistant.components.autoskope.models.Vehicle.from_api",
            side_effect=TypeError("Unexpected processing error"),
        ),
    ):
        response_data["cars"] = [{"id": "1"}]
        mock_client_response.text = AsyncMock(return_value=json.dumps(response_data))

        with pytest.raises(
            UpdateFailed,
            match="Unexpected error processing vehicle data: Unexpected processing error",
        ):
            await api.get_vehicles()


async def test_request_json_response(api: AutoskopeApi, mock_client_response) -> None:
    """Test _request handling a successful JSON response."""
    test_path = "/some/json/endpoint"
    expected_data = {"key": "value", "success": True}

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "application/json; charset=utf-8"}
    mock_client_response.text = AsyncMock(return_value=json.dumps(expected_data))

    with patch.object(api, "_get_session", return_value=mock_session):
        result = await api._request("post", test_path, data={"req": "data"})

        assert result == expected_data
        mock_session.request.assert_called_once_with(
            "post",
            f"{api._host}{test_path}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"req": "data"},
        )


async def test_request_json_response_not_dict(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test _request handling a JSON response that is not a dictionary."""
    test_path = "/some/json/list/endpoint"
    invalid_json_data = ["list", "not", "dict"]

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "application/json"}
    mock_client_response.text = AsyncMock(return_value=json.dumps(invalid_json_data))

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(
            CannotConnect, match="Received non-dictionary JSON response from API"
        ),
    ):
        await api._request("post", test_path, data={})


async def test_request_client_response_error(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test _request handling ClientResponseError (e.g., 404)."""
    test_path = "/not/found"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 404
    mock_client_response.headers = {}
    mock_client_response.text = AsyncMock(return_value="Not Found")

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(CannotConnect, match="API request failed with status 404"),
    ):
        await api._request("post", test_path, data={})


async def test_request_client_error(api: AutoskopeApi) -> None:
    """Test _request handling ClientError (e.g., connection refused)."""
    test_path = "/timeout/endpoint"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.side_effect = aiohttp.ClientError("Connection refused")

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(
            CannotConnect, match="Error connecting to Autoskope API: Connection refused"
        ),
    ):
        await api._request("post", test_path, data={})


async def test_request_other_non_json(api: AutoskopeApi, mock_client_response) -> None:
    """Test _request handling other non-JSON, non-login/info responses."""
    test_path = "/some/other/path"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "text/plain"}
    mock_client_response.text = AsyncMock(return_value="Some plain text response")

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(CannotConnect, match="Received invalid response from API"),
    ):
        await api._request("post", test_path, data={})


async def test_request_invalid_json_body_with_json_header(
    api: AutoskopeApi, mock_client_response
) -> None:
    """Test _request handling invalid JSON body with JSON content type."""
    test_path = "/invalid/json/body"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.return_value = mock_client_response
    mock_client_response.status = 200
    mock_client_response.headers = {"Content-Type": "application/json"}
    mock_client_response.text = AsyncMock(return_value="this is not json {")

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(CannotConnect, match="Received invalid response from API"),
    ):
        await api._request("post", test_path, data={})


async def test_request_unexpected_exception(api: AutoskopeApi) -> None:
    """Test _request handling unexpected exceptions."""
    test_path = "/unexpected/error"

    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_session.request.side_effect = ValueError("Something broke unexpectedly")

    with (
        patch.object(api, "_get_session", return_value=mock_session),
        pytest.raises(
            CannotConnect, match="Unexpected API error: Something broke unexpectedly"
        ),
    ):
        await api._request("post", test_path, data={})
