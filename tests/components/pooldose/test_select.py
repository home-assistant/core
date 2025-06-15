"""Tests for the Seko Pooldose selects."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.components.pooldose.pooldose_api import PooldoseAPIClient
from homeassistant.components.pooldose.select import PooldoseSelect


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
                "PDPR1H1HAW100_FW539187_mode": {
                    "current": 0,  # <-- Index statt Label!
                    "options": ["auto", "manual"],
                },
                "PDPR1H1HAW100_FW539187_state": {
                    "current": None,
                    "options": ["on", "off"],
                },
            }
        }
    }
    return coordinator


def test_select_current_option_and_options(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test that the select entity returns the correct current option and options."""
    options = [(0, "auto"), (1, "manual")]
    select = PooldoseSelect(
        mock_coordinator,
        mock_api,
        "Mode",
        "pooldose_mode",
        "PDPR1H1HAW100_FW539187_mode",
        options,
        "PDPR1H1HAW100_FW539187",  # serialnumber
        None,  # entity_category
        {},  # device_info_dict
        True,  # enabled_by_default
    )
    assert select.current_option == "auto"
    assert select.options == ["auto", "manual"]


def test_select_current_option_none(
    mock_coordinator: PooldoseCoordinator, mock_api: PooldoseAPIClient
) -> None:
    """Test that the select entity returns None if value is missing."""
    options = [(0, "on"), (1, "off")]
    select = PooldoseSelect(
        mock_coordinator,
        mock_api,
        "State",
        "pooldose_state",
        "PDPR1H1HAW100_FW539187_state",
        options,
        "PDPR1H1HAW100_FW539187",
        None,
        {},
        True,
    )
    assert select.current_option is None
    assert select.options == ["on", "off"]
