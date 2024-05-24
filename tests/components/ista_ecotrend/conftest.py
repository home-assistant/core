"""Common fixtures for the ista Ecotrend tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ista_ecotrend.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ista() -> Generator[MagicMock, None, None]:
    """Mock Pyecotrend_ista client."""
    with patch(
        "homeassistant.components.ista_ecotrend.config_flow.PyEcotrendIsta",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client._uuid = "26e93f1a-c828-11ea-87d0-0242ac130003"
        client.get_consumption_unit_details.return_value = {
            "consumptionUnits": [
                {
                    "id": "26e93f1a-c828-11ea-87d0-0242ac130003",
                    "address": {
                        "street": "Luxemburger Str.",
                        "houseNumber": "1",
                    },
                }
            ]
        }

        yield client
