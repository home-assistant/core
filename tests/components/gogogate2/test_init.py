"""Tests for the GogoGate2 component."""
import pytest

from homeassistant.components.gogogate2 import async_setup_entry
from homeassistant.components.gogogate2.common import GogoGateDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


async def test_auth_fail(hass: HomeAssistant) -> None:
    """Test authorization failures."""

    coordinator_mock: GogoGateDataUpdateCoordinator = MagicMock(
        spec=GogoGateDataUpdateCoordinator
    )
    coordinator_mock.last_update_success = False

    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gogogate2.get_data_update_coordinator",
        return_value=coordinator_mock,
    ), pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, config_entry)
