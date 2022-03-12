"""Tests for the SolarEdge coordinator services."""
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.solaredge.coordinator import SolarEdgeOverviewDataService
from homeassistant.helpers.update_coordinator import UpdateFailed

SITE_ID = "1a2b3c4d5e6f7g8h"

mock_overview_data = {
    "overview": {
        "lifeTimeData": {"energy": 100000},
        "lastYearData": {"energy": 50000},
        "lastMonthData": {"energy": 10000},
        "lastDayData": {"energy": 0.0},
        "currentPower": {"power": 0.0},
    }
}


@patch("solaredge.Solaredge")
def test_solaredgeoverviewdataservice_valid_energy_values(mock_solaredge):
    """Test valid no exception for valid overview data."""
    data_service = SolarEdgeOverviewDataService(Mock(), mock_solaredge, SITE_ID)

    # Valid data
    mock_solaredge.get_overview.return_value = mock_overview_data

    # No exception should be raised
    data_service.update()


@patch("solaredge.Solaredge")
def test_solaredgeoverviewdataservice_invalid_lifetime_energy(mock_solaredge):
    """Test update will be skipped for invalid energy values."""
    data_service = SolarEdgeOverviewDataService(Mock(), mock_solaredge, SITE_ID)

    invalid_data = mock_overview_data
    # Invalid energy values, lifeTimeData energy is lower than last year, month or day.
    invalid_data["overview"]["lifeTimeData"]["energy"] = 0
    mock_solaredge.get_overview.return_value = invalid_data

    # UpdateFailed exception should be raised
    with pytest.raises(UpdateFailed):
        data_service.update()


@patch("solaredge.Solaredge")
def test_solaredgeoverviewdataservice_invalid_year_energy(mock_solaredge):
    """Test update will be skipped for invalid energy values."""
    data_service = SolarEdgeOverviewDataService(Mock(), mock_solaredge, SITE_ID)

    invalid_data = mock_overview_data
    # Invalid energy values, lastYearData energy is lower than last month or day.
    invalid_data["overview"]["lastYearData"]["energy"] = 0
    mock_solaredge.get_overview.return_value = invalid_data

    # UpdateFailed exception should be raised
    with pytest.raises(UpdateFailed):
        data_service.update()


@patch("solaredge.Solaredge")
def test_solaredgeoverviewdataservice_valid_all_zero_energy(mock_solaredge):
    """Test update will not be skipped for valid energy values."""
    data_service = SolarEdgeOverviewDataService(Mock(), mock_solaredge, SITE_ID)

    invalid_data = mock_overview_data
    # Invalid energy values, lastYearData energy is lower than last month or day.
    invalid_data["overview"]["lifeTimeData"]["energy"] = 0.0
    invalid_data["overview"]["lastYearData"]["energy"] = 0.0
    invalid_data["overview"]["lastMonthData"]["energy"] = 0.0
    invalid_data["overview"]["lastDayData"]["energy"] = 0.0
    mock_solaredge.get_overview.return_value = invalid_data

    data_service.update()
