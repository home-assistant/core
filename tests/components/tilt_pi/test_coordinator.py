"""Tests for the Tilt Pi coordinator."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.tilt_pi.api import (
    TiltPiConnectionError,
    TiltPiConnectionTimeoutError,
)
from homeassistant.components.tilt_pi.coordinator import TiltPiDataUpdateCoordinator
from homeassistant.components.tilt_pi.model import TiltColor, TiltHydrometerData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_async_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test coordinator update with valid data."""
    mock_tiltpi_client.get_hydrometers.return_value = [
        TiltHydrometerData(
            mac_id="00:1A:2B:3C:4D:5E",
            color=TiltColor.BLACK,
            temperature=55.0,
            gravity=1.010,
        ),
        TiltHydrometerData(
            mac_id="00:1s:99:f1:d2:4f",
            color=TiltColor.YELLOW,
            temperature=68.0,
            gravity=1.015,
        ),
    ]

    coordinator = TiltPiDataUpdateCoordinator(
        hass, mock_config_entry, mock_tiltpi_client
    )
    data = await coordinator._async_update_data()

    assert len(data) == 2
    black_tilt = data[0]
    assert black_tilt.color == TiltColor.BLACK
    assert black_tilt.mac_id == "00:1A:2B:3C:4D:5E"
    assert black_tilt.temperature == 55.0
    assert black_tilt.gravity == 1.010
    yellow_tilt = data[1]
    assert yellow_tilt.color == TiltColor.YELLOW
    assert yellow_tilt.mac_id == "00:1s:99:f1:d2:4f"
    assert yellow_tilt.temperature == 68.0
    assert yellow_tilt.gravity == 1.015


async def test_coordinator_async_update_data_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test coordinator update with empty data."""
    mock_tiltpi_client.get_hydrometers.return_value = []

    coordinator = TiltPiDataUpdateCoordinator(
        hass, mock_config_entry, mock_tiltpi_client
    )
    data = await coordinator._async_update_data()

    assert len(data) == 0


async def test_coordinator_async_update_data_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test coordinator handling connection error."""
    mock_tiltpi_client.get_hydrometers.side_effect = TiltPiConnectionError("Test error")

    coordinator = TiltPiDataUpdateCoordinator(
        hass, mock_config_entry, mock_tiltpi_client
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_async_update_data_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tiltpi_client: MagicMock,
) -> None:
    """Test coordinator handling timeout error."""
    mock_tiltpi_client.get_hydrometers.side_effect = TiltPiConnectionTimeoutError(
        "Timeout"
    )

    coordinator = TiltPiDataUpdateCoordinator(
        hass, mock_config_entry, mock_tiltpi_client
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
