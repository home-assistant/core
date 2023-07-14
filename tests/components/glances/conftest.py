"""Conftest for speedtestdotnet."""
from unittest.mock import AsyncMock, patch

import pytest

from . import HA_SENSOR_DATA


@pytest.fixture(autouse=True)
def mock_api():
    """Mock glances api."""
    with patch("homeassistant.components.glances.Glances") as mock_api:
        mock_api.return_value.get_ha_sensor_data = AsyncMock(
            return_value=HA_SENSOR_DATA
        )
        yield mock_api
