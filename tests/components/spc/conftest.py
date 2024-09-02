"""Tests for Vanderbilt SPC component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pyspcwebgw
import pytest


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the SPC client."""

    with patch(
        "homeassistant.components.spc.SpcWebGateway", autospec=True
    ) as mock_client:
        client = mock_client.return_value
        client.async_load_parameters.return_value = True
        mock_area = AsyncMock(spec=pyspcwebgw.area.Area)
        mock_area.id = "1"
        mock_area.mode = pyspcwebgw.const.AreaMode.FULL_SET
        mock_area.last_changed_by = "Sven"
        mock_area.name = "House"
        mock_area.verified_alarm = False
        client.areas = {"1": mock_area}
        yield mock_client
