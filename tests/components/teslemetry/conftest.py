"""Test fixtures for Teslemetry component."""

from collections.abc import Generator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from teslemetry_stream.stream import recursive_match

from homeassistant.components.teslemetry.const import TOKEN_URL

from .const import (
    COMMAND_OK,
    ENERGY_HISTORY,
    LIVE_STATUS,
    METADATA,
    METADATA_ENERGY,
    METADATA_LEGACY,
    PRODUCTS,
    PRODUCTS_ENERGY,
    SITE_INFO,
    VEHICLE_DATA,
    WAKE_UP_ONLINE,
)

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_setup_entry():
    """Mock Teslemetry async_setup_entry method."""
    with patch(
        "homeassistant.components.teslemetry.async_setup_entry", return_value=True
    ) as mock_async_setup_entry:
        yield mock_async_setup_entry


@pytest.fixture
def mock_token_response() -> dict[str, Any]:
    """Return a mock OAuth token response."""
    return {
        "refresh_token": "mock-refresh-token",
        "access_token": "mock-access-token",
        "type": "Bearer",
        "expires_in": 60,
    }


@pytest.fixture
def mock_token_post(
    aioclient_mock: AiohttpClientMocker, mock_token_response: dict[str, Any]
) -> None:
    """Mock the OAuth token endpoint."""
    aioclient_mock.post(TOKEN_URL, json=mock_token_response)


@pytest.fixture(autouse=True)
def mock_metadata():
    """Mock Tesla Fleet Api metadata method."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata", return_value=METADATA
    ) as mock_products:
        yield mock_products


@pytest.fixture(autouse=True)
def mock_products():
    """Mock Tesla Fleet Api products method."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.products", return_value=PRODUCTS
    ) as mock_products:
        yield mock_products


@pytest.fixture(autouse=True)
def mock_vehicle_data() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific vehicle_data method."""
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.vehicle_data",
        return_value=VEHICLE_DATA,
    ) as mock_vehicle_data:
        yield mock_vehicle_data


@pytest.fixture
def mock_legacy():
    """Mock Tesla Fleet Api products method."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry.metadata", return_value=METADATA_LEGACY
    ) as mock_products:
        yield mock_products


@pytest.fixture(autouse=True)
def mock_wake_up():
    """Mock Tesla Fleet API Vehicle Specific wake_up method."""
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.wake_up",
        return_value=WAKE_UP_ONLINE,
    ) as mock_wake_up:
        yield mock_wake_up


@pytest.fixture(autouse=True)
def mock_vehicle() -> Generator[AsyncMock]:
    """Mock Tesla Fleet API Vehicle Specific vehicle method."""
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.vehicle",
        return_value=WAKE_UP_ONLINE,
    ) as mock_vehicle:
        yield mock_vehicle


@pytest.fixture(autouse=True)
def mock_request():
    """Mock Tesla Fleet API Vehicle Specific class."""
    with patch(
        "tesla_fleet_api.teslemetry.Teslemetry._request",
        return_value=COMMAND_OK,
    ) as mock_request:
        yield mock_request


@pytest.fixture(autouse=True)
def mock_live_status():
    """Mock Teslemetry Energy Specific live_status method."""
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.live_status",
        side_effect=lambda: deepcopy(LIVE_STATUS),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_site_info():
    """Mock Teslemetry Energy Specific site_info method."""
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.site_info",
        side_effect=lambda: deepcopy(SITE_INFO),
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_energy_history():
    """Mock Teslemetry Energy Specific site_info method."""
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.energy_history",
        return_value=ENERGY_HISTORY,
    ) as mock_live_status:
        yield mock_live_status


@pytest.fixture(autouse=True)
def mock_stream_listen():
    """Mock Teslemetry Stream listen method."""
    with patch(
        "teslemetry_stream.TeslemetryStream.listen",
    ) as mock_stream_listen:
        yield mock_stream_listen


@pytest.fixture(autouse=True)
def mock_add_listener():
    """Mock Teslemetry Stream add listener method."""
    with patch(
        "teslemetry_stream.TeslemetryStream.async_add_listener",
    ) as mock_add_listener:
        mock_add_listener.listeners = []

        def unsubscribe() -> None:
            return

        def side_effect(callback, filters):
            mock_add_listener.listeners.append((callback, filters))
            return unsubscribe

        def send(event) -> None:
            for listener, filters in mock_add_listener.listeners:
                if recursive_match(filters, event):
                    listener(event)

        mock_add_listener.send = send
        mock_add_listener.side_effect = side_effect
        yield mock_add_listener


@pytest.fixture
def mock_add_connection_listener():
    """Mock Teslemetry Stream add connection listener method."""
    with patch(
        "teslemetry_stream.TeslemetryStream.async_add_connection_listener",
    ) as mock_add_connection_listener:
        mock_add_connection_listener.listeners = []

        def unsubscribe() -> None:
            return

        def side_effect(callback):
            mock_add_connection_listener.listeners.append(callback)
            return unsubscribe

        def send(connected: bool) -> None:
            for listener in mock_add_connection_listener.listeners:
                listener(connected)

        mock_add_connection_listener.send = send
        mock_add_connection_listener.side_effect = side_effect
        yield mock_add_connection_listener


@pytest.fixture
def mock_energy_live_stream() -> Generator[MagicMock]:
    """Capture the callback the integration registers for live_status events."""
    with patch(
        "teslemetry_stream.TeslemetryStreamEnergySite.listen_LiveStatus",
    ) as mock_listen:
        callbacks: list = []

        def side_effect(callback):
            callbacks.append(callback)
            return MagicMock()

        def send(live_status: dict) -> None:
            for callback in callbacks:
                callback(live_status)

        mock_listen.side_effect = side_effect
        mock_listen.send = send
        yield mock_listen


@pytest.fixture
def mock_energy_info_stream() -> Generator[MagicMock]:
    """Capture the callback the integration registers for site_info events."""
    with patch(
        "teslemetry_stream.TeslemetryStreamEnergySite.listen_SiteInfo",
    ) as mock_listen:
        callbacks: list = []

        def side_effect(callback):
            callbacks.append(callback)
            return MagicMock()

        def send(site_info: dict) -> None:
            for callback in callbacks:
                callback(site_info)

        mock_listen.side_effect = side_effect
        mock_listen.send = send
        yield mock_listen


@pytest.fixture
def mock_energy_tariff_stream() -> Generator[MagicMock]:
    """Capture the callback the integration registers for tariff events."""
    with patch(
        "teslemetry_stream.TeslemetryStreamEnergySite.listen_TariffContentV2",
    ) as mock_listen:
        callbacks: list = []

        def side_effect(callback):
            callbacks.append(callback)
            return MagicMock()

        def send(tariff: dict | None) -> None:
            for callback in callbacks:
                callback(tariff)

        mock_listen.side_effect = side_effect
        mock_listen.send = send
        yield mock_listen


@pytest.fixture
def mock_energy_only(mock_products: AsyncMock, mock_metadata: MagicMock) -> None:
    """Patch products and metadata to an energy-only account."""
    mock_products.return_value = PRODUCTS_ENERGY
    mock_metadata.return_value = METADATA_ENERGY


@pytest.fixture(autouse=True)
def mock_stream_get_config():
    """Mock Teslemetry Stream listen method."""
    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.get_config",
    ) as mock_stream_get_config:
        yield mock_stream_get_config


@pytest.fixture(autouse=True)
def mock_stream_update_config():
    """Mock Teslemetry Stream listen method."""
    with patch(
        "teslemetry_stream.TeslemetryStreamVehicle.update_config",
    ) as mock_stream_update_config:
        yield mock_stream_update_config


@pytest.fixture(autouse=True)
def mock_stream_connected():
    """Mock Teslemetry Stream listen method."""
    with patch(
        "teslemetry_stream.TeslemetryStream.connected",
        return_value=True,
    ) as mock_stream_connected:
        yield mock_stream_connected
