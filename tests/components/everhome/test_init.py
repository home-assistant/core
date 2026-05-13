"""Tests for the everHome/EcoTracker integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_connection_failed(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device registry integration."""
    mock_everhome_client.async_update.return_value = False
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
