"""Tests for the DVLA data update coordinator."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aio_dvla_vehicle_enquiry import DVLAError
import pytest

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.components.dvla.coordinator import DVLACoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def create_coordinator(
    hass: HomeAssistant,
    session: MagicMock,
    reg_number: str = "AB12CDE",
) -> DVLACoordinator:
    """Create a DVLA coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=reg_number,
        data={
            CONF_REG_NUMBER: reg_number,
        },
    )
    entry.add_to_hass(hass)

    return DVLACoordinator(
        hass,
        entry,
        session,
        reg_number,
    )


async def test_async_update_data_returns_vehicle_data(hass: HomeAssistant) -> None:
    """Test coordinator returns vehicle data from the DVLA client."""
    vehicle_data: dict[str, Any] = {
        "registrationNumber": "AB12CDE",
        "make": "FORD",
        "taxStatus": "Taxed",
    }
    session = MagicMock()
    coordinator = create_coordinator(hass, session)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        new_callable=AsyncMock,
    ) as mock_get_vehicle:
        mock_get_vehicle.return_value = vehicle_data

        result = await coordinator._async_update_data()

    assert result == vehicle_data
    mock_get_vehicle.assert_awaited_once_with("AB12CDE")


async def test_async_update_data_normalizes_registration_number(
    hass: HomeAssistant,
) -> None:
    """Test coordinator strips spaces and uppercases the registration number."""
    session = MagicMock()
    coordinator = create_coordinator(hass, session, "ab12 cde")

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        new_callable=AsyncMock,
    ) as mock_get_vehicle:
        mock_get_vehicle.return_value = {
            "registrationNumber": "AB12CDE",
            "make": "FORD",
        }

        await coordinator._async_update_data()

    mock_get_vehicle.assert_awaited_once_with("AB12CDE")


async def test_async_update_data_raises_update_failed_on_dvla_error(
    hass: HomeAssistant,
) -> None:
    """Test coordinator raises UpdateFailed on DVLA client errors."""
    session = MagicMock()
    coordinator = create_coordinator(hass, session)

    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        new_callable=AsyncMock,
    ) as mock_get_vehicle:
        mock_get_vehicle.side_effect = DVLAError("Vehicle not found")

        with pytest.raises(UpdateFailed, match="Vehicle not found"):
            await coordinator._async_update_data()
