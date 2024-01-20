"""Fixtures for Tessie."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from .const import PRODUCTS, VEHICLE_DATA, WAKE_UP_SUCCESS


@pytest.fixture(autouse=True)
def mock_teslemetry():
    """Mock Tesla api class."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry",
    ) as mock_teslemetry:
        mock_teslemetry.vehicle.specific.return_value.vehicle_data = AsyncMock(
            return_value=VEHICLE_DATA
        )
        mock_teslemetry.return_value.products = AsyncMock(return_value=PRODUCTS)

        mock_teslemetry.return_value.vehicle.specific.return_value.wake_up = AsyncMock(
            return_value=WAKE_UP_SUCCESS
        )
        mock_teslemetry.return_value.vehicle.specific.return_value.vehicle_data = (
            AsyncMock(return_value=VEHICLE_DATA)
        )
        mock_teslemetry._request.return_value = AsyncMock(
            {"response": None, "error": None}
        )
        yield mock_teslemetry
