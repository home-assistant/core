"""Test suez water coordinator."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components.suez_water.const import DOMAIN
from homeassistant.components.suez_water.coordinator import SuezWaterCoordinator
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DATA


async def test_coordinator_creation(hass: HomeAssistant) -> None:
    """Test creating coordinator."""

    coordinator = SuezWaterCoordinator(hass, None, MOCK_DATA["counter_id"])
    assert coordinator.always_update is True
    assert coordinator.update_interval is not None
    assert (
        coordinator.update_interval.total_seconds()
        == timedelta(hours=12).total_seconds()
    )
    assert coordinator.name is DOMAIN
    assert coordinator.aggregated_data is None


async def test_coordinator_setup(mock_coordinator: SuezWaterCoordinator) -> None:
    """Test coodinator setup."""

    # Nothing done for now
    await mock_coordinator._async_setup()
    assert mock_coordinator.setup_method is None


@freeze_time(datetime.now())
async def test_coordinator_update(mock_coordinator: SuezWaterCoordinator) -> None:
    """Test coordinator data update."""
    now = datetime.now()
    with (
        patch(
            "homeassistant.components.suez_water.coordinator.SuezWaterCoordinator._update_aggregated_historical_sensor"
        ),
    ):
        data = await mock_coordinator._async_update_data()
        assert mock_coordinator.last_update_success is True
        assert data is not None
        assert data["update"] == now
