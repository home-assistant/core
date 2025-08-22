"""Test the Pooldose coordinator."""

from pooldose.request_status import RequestStatus
import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import SERIAL_NUMBER

from tests.common import MockConfigEntry


async def test_coordinator_setup_success(
    hass: HomeAssistant,
    mock_pooldose_client,
    mock_config_entry: MockConfigEntry,
    mock_instant_values: dict,
    mock_device_info,
) -> None:
    """Test successful coordinator setup and data fetch."""
    mock_pooldose_client.instant_values.return_value = (
        RequestStatus.SUCCESS,
        mock_instant_values,
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_pooldose_client,
        mock_config_entry,
    )

    await coordinator._async_setup()
    assert coordinator.device_info == mock_pooldose_client.device_info

    assert coordinator.device_info["serial_number"] == SERIAL_NUMBER
    assert coordinator.device_info["identifiers"] == {("pooldose", SERIAL_NUMBER)}

    await coordinator.async_refresh()
    assert coordinator.data is not None
    assert coordinator.last_update_success is True

    data = coordinator.data
    assert isinstance(data, dict)
    assert "deviceInfo" in data
    assert data["deviceInfo"]["dwi_status"] == "ok"

    mock_pooldose_client.instant_values.assert_called_once()


async def test_coordinator_device_info_persistence(
    hass: HomeAssistant,
    mock_pooldose_client,
    mock_config_entry: MockConfigEntry,
    mock_device_info,
) -> None:
    """Test that device info is properly stored and accessible."""
    coordinator = PooldoseCoordinator(
        hass,
        mock_pooldose_client,
        mock_config_entry,
    )

    await coordinator._async_setup()

    device_info = coordinator.device_info
    assert device_info["identifiers"] == {("pooldose", SERIAL_NUMBER)}
    assert device_info["name"] == "PoolDose Device"
    assert device_info["manufacturer"] == "SEKO"
    assert device_info["model"] == "PDPR1H1HAW100"
    assert device_info["serial_number"] == SERIAL_NUMBER
    assert device_info["hw_version"] == "FW539187"


async def test_coordinator_handles_connection_error(
    hass: HomeAssistant,
    mock_pooldose_client,
    mock_config_entry: MockConfigEntry,
    mock_device_info,
) -> None:
    """Test that the coordinator handles connection errors gracefully."""
    mock_pooldose_client.instant_values.side_effect = ConnectionError(
        "Connection failed"
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_pooldose_client,
        mock_config_entry,
    )

    # Set up the coordinator first to initialize device_info
    await coordinator._async_setup()

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.data is None

    assert coordinator.device_info["serial_number"] == SERIAL_NUMBER
    mock_pooldose_client.instant_values.assert_called_once()


async def test_coordinator_handles_api_error_status(
    hass: HomeAssistant,
    mock_pooldose_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the coordinator handles API error status."""
    mock_pooldose_client.instant_values.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        None,
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_pooldose_client,
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.data is None
    mock_pooldose_client.instant_values.assert_called_once()


async def test_coordinator_internal_update_method(
    hass: HomeAssistant,
    mock_pooldose_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the internal _async_update_data method directly."""
    coordinator = PooldoseCoordinator(
        hass,
        mock_pooldose_client,
        mock_config_entry,
    )

    mock_pooldose_client.instant_values.side_effect = ConnectionError(
        "Connection failed"
    )

    with pytest.raises(
        UpdateFailed, match="Failed to connect to PoolDose device while fetching data"
    ):
        await coordinator._async_update_data()

    mock_pooldose_client.instant_values.side_effect = TimeoutError("Request timed out")

    with pytest.raises(
        UpdateFailed, match="Timeout fetching data from PoolDose device"
    ):
        await coordinator._async_update_data()

    mock_pooldose_client.instant_values.side_effect = OSError("Network unreachable")

    with pytest.raises(
        UpdateFailed, match="Failed to connect to PoolDose device while fetching data"
    ):
        await coordinator._async_update_data()

    mock_pooldose_client.instant_values.side_effect = None
    mock_pooldose_client.instant_values.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        None,
    )

    with pytest.raises(UpdateFailed, match="API returned status"):
        await coordinator._async_update_data()

    mock_pooldose_client.instant_values.return_value = (RequestStatus.SUCCESS, None)

    with pytest.raises(UpdateFailed, match="No data received from API"):
        await coordinator._async_update_data()
