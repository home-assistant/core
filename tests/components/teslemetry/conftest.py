"""Fixtures for Tessie."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.teslemetry.const import DOMAIN

from tests.common import load_json_object_fixture


@pytest.fixture(autouse=True)
def mock_teslemetry():
    """Mock Tesla api class."""
    with patch(
        "homeassistant.components.teslemetry.Teslemetry",
    ) as mock_teslemetry:
        mock_teslemetry.vehicle.specific.return_value.vehicle_data = AsyncMock(
            load_json_object_fixture("vehicle_data.json", DOMAIN)
        )
        # mock_teslemetry._request.return_value = AsyncMock(
        #    {"response": None, "error": None}
        # )
        yield mock_teslemetry
