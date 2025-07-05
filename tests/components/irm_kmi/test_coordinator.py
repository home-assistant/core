"""Tests for the coordinator of IRM KMI integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.irm_kmi.coordinator import IrmKmiCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_update_interval_is_7_minutes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the refresh interval 7 minutes.

    If you need to change this test, also change the documentation: https://github.com/home-assistant/home-assistant.io.
    """

    coordinator = IrmKmiCoordinator(hass, mock_config_entry, MagicMock())

    assert timedelta(minutes=7) == coordinator.update_interval
