"""Tests for sensors used to report data from the combined energy API."""
from datetime import datetime
from unittest.mock import AsyncMock

from combined_energy import models
import pytest

from homeassistant.components.combined_energy import binary_sensor
from homeassistant.components.combined_energy.coordinator import (
    CombinedEnergyConnectivityDataService,
)


class TestCombinedEnergyConnectedSensor:
    """Test cases for CombinedEnergyConnectedSensor."""

    @pytest.fixture
    def data_service(self):
        """Mock data service."""
        return AsyncMock(
            CombinedEnergyConnectivityDataService,
            api=AsyncMock(installation_id=999999),
            coordinator=AsyncMock(),
        )

    def test_initialise(self, data_service) -> None:
        """Test initialisation generates expected names."""
        target = binary_sensor.CombinedEnergyConnectedSensor("Test", data_service)

        assert target.unique_id == "install_999999-connected"

    def test_is_on__where_no_data(self, data_service) -> None:
        """Test is_on where no data has been collected."""
        data_service.data = None
        target = binary_sensor.CombinedEnergyConnectedSensor("Test", data_service)

        actual = target.is_on

        assert actual is None

    @pytest.mark.parametrize("connected", (True, False))
    def test_is_on__where_connected_status_set(self, data_service, connected) -> None:
        """Test is_on where Connected status is set."""
        data_service.data = models.ConnectionStatus(
            status="OK",
            installationId=999999,
            connected=connected,
            since=datetime(2022, 11, 11, 11, 11, 11),
        )
        target = binary_sensor.CombinedEnergyConnectedSensor("Test", data_service)

        actual = target.is_on

        assert actual is connected
