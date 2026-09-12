"""Fixtures for Tewke integration tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytewke import ConfigData

from homeassistant.components.tewke.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_tap():
    """Mock pytewke.Tap."""
    with patch("pytewke.Tap", autospec=True) as mock_tap_class:
        tap_instance = AsyncMock()
        tap_instance.resources = {}
        tap_instance.discover = AsyncMock()
        tap_instance.get_scenes = AsyncMock(return_value={})
        tap_instance.get_targets = AsyncMock(return_value={})
        tap_instance.get_sensors = AsyncMock(return_value=None)
        tap_instance.get_radar = AsyncMock(return_value=None)
        tap_instance.get_energy = AsyncMock(return_value=None)
        tap_instance.get_energy_override = AsyncMock(return_value=None)

        mock_config = ConfigData.model_construct(
            hardwareId="test_dock_id",
        )
        tap_instance.get_config = AsyncMock(return_value=mock_config)
        tap_instance.close = AsyncMock()
        tap_instance.clear_callbacks = MagicMock()
        tap_instance.wall_dock_id = "test_dock_id"
        mock_tap_class.return_value = tap_instance
        yield tap_instance


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_dock_id",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Tewke Switch",
        },
        options={
            "room_name": "Living Room",
        },
    )
