"""Fixtures for the DVLA integration tests."""

from collections.abc import Awaitable, Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.dvla.const import CONF_REG_NUMBER, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_REG_NUMBER = "AB12CDE"

MOCK_VEHICLE_DATA: dict[str, Any] = {
    "registrationNumber": MOCK_REG_NUMBER,
    "taxStatus": "Taxed",
    "taxDueDate": "2026-03-01",
    "engineCapacity": 1998,
    "co2Emissions": 150,
    "markedForExport": False,
    "make": "FORD",
    "motStatus": "Valid",
    "motExpiryDate": "2026-11-30",
    "monthOfFirstRegistration": "2024-05",
    "yearOfManufacture": 2020,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock DVLA config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_REG_NUMBER,
        data={CONF_REG_NUMBER: MOCK_REG_NUMBER},
    )


@pytest.fixture
def mock_dvla_client() -> Generator[AsyncMock]:
    """Mock the DVLA client vehicle lookup."""
    with patch(
        "homeassistant.components.dvla.coordinator.DVLAClient.async_get_vehicle",
        return_value=MOCK_VEHICLE_DATA,
    ) as mock_get_vehicle:
        yield mock_get_vehicle


@pytest.fixture
def setup_dvla_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
) -> Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]]:
    """Return a helper to set up the DVLA integration."""

    async def _setup(vehicle_data: dict[str, Any] | None = None) -> MockConfigEntry:
        if vehicle_data is not None:
            mock_dvla_client.return_value = vehicle_data

        mock_config_entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry

    return _setup
