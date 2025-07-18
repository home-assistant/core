"""Test the Pooldose coordinator."""

import datetime
from unittest.mock import AsyncMock

from pooldose.request_status import RequestStatus
import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain="pooldose",
        title="PoolDose",
        data={"host": "192.168.1.100"},
        unique_id="PDPR1H1HAW100_FW539187",
    )


@pytest.fixture
def mock_client() -> AsyncMock:
    """Return a mock client."""
    return AsyncMock()


@pytest.fixture
def mock_instant_values() -> dict:
    """Return realistic instant values data structure."""
    return {
        "deviceInfo": {"dwi_status": "ok", "modbus_status": "on"},
        "collapsed_bar": [],
        "PDPR1H1HAW100_FW539187_w_1ekeigkin": {
            "visible": True,
            "alarm": False,
            "current": 7.6,
            "resolution": 0.1,
            "magnitude": ["pH", "PH"],
            "absMin": 0,
            "absMax": 14,
            "minT": 6,
            "maxT": 8,
        },
        "PDPR1H1HAW100_FW539187_w_1eklenb23": {
            "visible": True,
            "alarm": False,
            "current": 707,
            "resolution": 1,
            "magnitude": ["mV", "MV"],
            "absMin": -99,
            "absMax": 999,
            "minT": 600,
            "maxT": 800,
        },
        "PDPR1H1HAW100_FW539187_w_1eommf39k": {
            "visible": True,
            "alarm": False,
            "current": 29.5,
            "resolution": 0.1,
            "magnitude": ["°C", "CDEG"],
            "absMin": 0,
            "absMax": 55,
            "minT": 10,
            "maxT": 38,
        },
        "PDPR1H1HAW100_FW539187_w_1eklg44ro": {
            "visible": True,
            "current": "|PDPR1H1HAW100_FW539187_LABEL_w_1eklg44ro_ALCALYNE|",
            "resolution": 1,
            "magnitude": ["UNDEFINED", "UNDEFINED"],
            "absMin": 0,
            "absMax": 1,
        },
    }


@pytest.mark.asyncio
async def test_coordinator_successful_data_fetch(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_instant_values: dict,
) -> None:
    """Test that the coordinator successfully fetches and processes data."""
    mock_client.instant_values.return_value = (
        RequestStatus.SUCCESS,
        mock_instant_values,
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.last_update_success is True
    assert coordinator.available is True

    status, data = coordinator.data
    assert status == RequestStatus.SUCCESS
    assert isinstance(data, dict)
    assert "deviceInfo" in data
    assert data["deviceInfo"]["dwi_status"] == "ok"
    assert "PDPR1H1HAW100_FW539187_w_1ekeigkin" in data
    assert data["PDPR1H1HAW100_FW539187_w_1ekeigkin"]["current"] == 7.6

    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_connection_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles connection errors gracefully."""
    mock_client.instant_values.side_effect = ConnectionError("Connection failed")

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # DataUpdateCoordinator catches UpdateFailed and sets last_update_success=False
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.available is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_timeout_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles timeout errors gracefully."""
    mock_client.instant_values.side_effect = TimeoutError("Request timed out")

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # DataUpdateCoordinator catches UpdateFailed and sets last_update_success=False
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.available is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_os_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles OS errors gracefully."""
    mock_client.instant_values.side_effect = OSError("Network unreachable")

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # DataUpdateCoordinator catches UpdateFailed and sets last_update_success=False
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.available is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_api_error_status(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles API error status."""
    mock_client.instant_values.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        None,
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # DataUpdateCoordinator catches UpdateFailed and sets last_update_success=False
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.available is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_none_data(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles None data response."""
    mock_client.instant_values.return_value = (RequestStatus.SUCCESS, None)

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # DataUpdateCoordinator catches UpdateFailed and sets last_update_success=False
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.available is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_generic_exception(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles generic exceptions gracefully."""
    mock_client.instant_values.side_effect = Exception("Unexpected error")

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # DataUpdateCoordinator catches UpdateFailed and sets last_update_success=False
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.available is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_availability_state_changes(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_instant_values: dict,
) -> None:
    """Test the coordinator's availability property changes correctly."""
    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # Initially not available (no data fetched yet)
    assert coordinator.available is False

    # Successful fetch makes it available
    mock_client.instant_values.return_value = (
        RequestStatus.SUCCESS,
        mock_instant_values,
    )
    await coordinator.async_refresh()
    assert coordinator.available is True

    # API failure makes it unavailable
    mock_client.instant_values.side_effect = ConnectionError("Connection failed")
    await coordinator.async_refresh()
    assert coordinator.available is False

    # Recovery makes it available again
    mock_client.instant_values.side_effect = None
    mock_client.instant_values.return_value = (
        RequestStatus.SUCCESS,
        mock_instant_values,
    )
    await coordinator.async_refresh()
    assert coordinator.available is True


@pytest.mark.asyncio
async def test_coordinator_data_structure_validation(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator validates data structure properly."""
    # Test with empty data
    mock_client.instant_values.return_value = (RequestStatus.SUCCESS, {})

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.last_update_success is True
    assert coordinator.available is True

    status, data = coordinator.data
    assert status == RequestStatus.SUCCESS
    assert data == {}
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_multiple_refresh_cycles(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_instant_values: dict,
) -> None:
    """Test that the coordinator handles multiple refresh cycles correctly."""
    mock_client.instant_values.return_value = (
        RequestStatus.SUCCESS,
        mock_instant_values,
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # First refresh
    await coordinator.async_refresh()
    assert coordinator.available is True
    assert coordinator.last_update_success is True

    # Second refresh with updated data
    updated_data = mock_instant_values.copy()
    updated_data["PDPR1H1HAW100_FW539187_w_1ekeigkin"]["current"] = 8.0
    mock_client.instant_values.return_value = (RequestStatus.SUCCESS, updated_data)

    await coordinator.async_refresh()
    assert coordinator.available is True
    assert coordinator.last_update_success is True

    status, data = coordinator.data
    assert data["PDPR1H1HAW100_FW539187_w_1ekeigkin"]["current"] == 8.0
    assert mock_client.instant_values.call_count == 2


@pytest.mark.asyncio
async def test_coordinator_internal_update_method(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the internal _async_update_data method directly."""
    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # Test ConnectionError is properly raised
    mock_client.instant_values.side_effect = ConnectionError("Connection failed")

    with pytest.raises(UpdateFailed, match="Failed to connect to PoolDose device"):
        await coordinator._async_update_data()

    # Test TimeoutError is properly raised
    mock_client.instant_values.side_effect = TimeoutError("Request timed out")

    with pytest.raises(
        UpdateFailed, match="Timeout communicating with PoolDose device"
    ):
        await coordinator._async_update_data()

    # Test OSError is properly raised
    mock_client.instant_values.side_effect = OSError("Network unreachable")

    with pytest.raises(UpdateFailed, match="Failed to connect to PoolDose device"):
        await coordinator._async_update_data()

    # Test generic Exception is properly raised
    mock_client.instant_values.side_effect = Exception("Unexpected error")

    with pytest.raises(
        UpdateFailed, match="Unexpected error communicating with device"
    ):
        await coordinator._async_update_data()

    # Test API error status
    mock_client.instant_values.side_effect = None
    mock_client.instant_values.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        None,
    )

    with pytest.raises(UpdateFailed, match="API returned status"):
        await coordinator._async_update_data()

    # Test None data
    mock_client.instant_values.return_value = (RequestStatus.SUCCESS, None)

    with pytest.raises(UpdateFailed, match="No data received from API"):
        await coordinator._async_update_data()
