"""Tests for the coordinator of IRM KMI integration."""

from datetime import timedelta

from homeassistant.components.irm_kmi.coordinator import IrmKmiCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_jules_forgot_to_revert_update_interval_before_pushing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the refresh interval is more than 5 minutes."""
    coordinator = IrmKmiCoordinator(hass, mock_config_entry)

    assert timedelta(minutes=5) <= coordinator.update_interval
