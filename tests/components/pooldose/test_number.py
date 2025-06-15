"""Tests for the Seko Pooldose numbers."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.number import PooldoseNumber
from homeassistant.components.pooldose.pooldose_api import PooldoseAPIClient


@pytest.fixture
def mock_api() -> PooldoseAPIClient:
    """Return a mocked PooldoseAPIClient."""
    api = MagicMock(spec=PooldoseAPIClient)
    api.serial_key = "PDPR1H1HAW100_FW539187"
    return api


@pytest.fixture
def mock_coordinator() -> PooldoseCoordinator:
    """Return a mocked PooldoseCoordinator."""
    coordinator = MagicMock(spec=PooldoseCoordinator)
    coordinator.data = {
        "devicedata": {
            "PDPR1H1HAW100_FW539187": {
                "PDPR1H1HAW100_FW539187_setpoint": {"current": 7.5},
                "PDPR1H1HAW100_FW539187_limit": {"current": None},
            }
        }
    }
    return coordinator


def test_number_native_value(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test that the number entity returns the correct value."""
    defaults = {"min": 0, "max": 14, "step": 0.1, "default": 7.0, "unit": "pH"}
    number = PooldoseNumber(
        mock_coordinator,
        mock_api,
        "Setpoint",
        "pooldose_setpoint",
        "PDPR1H1HAW100_FW539187_setpoint",
        defaults,
        "PDPR1H1HAW100_FW539187",
        None,
        None,
        {},
        True,
    )
    assert number.native_value == 7.5


def test_number_native_value_none(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test that the number entity returns None if value is missing."""
    defaults = {"min": 0, "max": 14, "step": 0.1, "default": 7.0, "unit": "pH"}
    number = PooldoseNumber(
        mock_coordinator,
        mock_api,
        "Limit",
        "pooldose_limit",
        "PDPR1H1HAW100_FW539187_limit",
        defaults,
        "PDPR1H1HAW100_FW539187",
        None,
        None,
        {},
        True,
    )
    assert number.native_value is None
