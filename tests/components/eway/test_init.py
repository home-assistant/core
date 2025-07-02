"""Test the Eway integration init."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "homeassistant" / "components" / "eway"))

# Import the integration modules
try:
    from homeassistant.components.eway import (
        PLATFORMS,
        async_setup,
        async_setup_entry,
        async_unload_entry,
    )
    from homeassistant.components.eway.const import DOMAIN
    from homeassistant.components.eway.coordinator import EwayDataUpdateCoordinator
except ImportError:
    # Fallback to direct imports
    from const import DOMAIN

    import __init__ as eway_init
    from homeassistant.components.eway.coordinator import EwayDataUpdateCoordinator

    PLATFORMS = eway_init.PLATFORMS
    async_setup = eway_init.async_setup
    async_setup_entry = eway_init.async_setup_entry
    async_unload_entry = eway_init.async_unload_entry


class TestEwayInit:
    """Test the Eway integration initialization."""

    async def test_async_setup(self, hass: HomeAssistant):
        """Test async_setup function."""
        config: ConfigType = {}

        result = await async_setup(hass, config)

        assert result is True
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN] == {}

    async def test_async_setup_entry_success(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test successful setup of config entry."""
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ) as mock_forward:
            mock_forward.return_value = True

            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert isinstance(
                hass.data[DOMAIN][mock_config_entry.entry_id], EwayDataUpdateCoordinator
            )

            # Verify that platforms are set up
            mock_forward.assert_called_once_with(mock_config_entry, PLATFORMS)

    async def test_async_setup_entry_coordinator_refresh_failure(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test setup entry when coordinator refresh fails."""
        with patch(
            "homeassistant.components.eway.coordinator.EwayDataUpdateCoordinator.async_config_entry_first_refresh"
        ) as mock_refresh:
            mock_refresh.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await async_setup_entry(hass, mock_config_entry)

    async def test_async_unload_entry_success(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test successful unload of config entry."""
        # First set up the entry
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ):
            await async_setup_entry(hass, mock_config_entry)

        # Now test unloading
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms"
        ) as mock_unload:
            mock_unload.return_value = True

            result = await async_unload_entry(hass, mock_config_entry)

            assert result is True
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

            # Verify that platforms are unloaded
            mock_unload.assert_called_once_with(mock_config_entry, PLATFORMS)

    async def test_async_unload_entry_failure(
        self, hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_aioeway_module
    ):
        """Test unload entry when platform unload fails."""
        # First set up the entry
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ):
            await async_setup_entry(hass, mock_config_entry)

        # Now test unloading with failure
        with patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms"
        ) as mock_unload:
            mock_unload.return_value = False

            result = await async_unload_entry(hass, mock_config_entry)

            assert result is False
            # Entry should still be in hass.data since unload failed
            assert mock_config_entry.entry_id in hass.data[DOMAIN]

    def test_platforms_constant(self):
        """Test that PLATFORMS constant is correctly defined."""
        assert PLATFORMS == [Platform.SENSOR]
        assert len(PLATFORMS) == 1
        assert Platform.SENSOR in PLATFORMS

    async def test_multiple_entries(self, hass: HomeAssistant, mock_aioeway_module):
        """Test handling multiple config entries."""
        # Create two different config entries
        entry1 = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Eway Inverter 1",
            data={
                "mqtt_host": "test1.mqtt.broker",
                "mqtt_port": 1883,
                "mqtt_username": "test_user1",
                "mqtt_password": "test_password1",
                "device_id": "device1",
                "device_sn": "sn1",
                "device_model": "model1",
                "scan_interval": 30,
                "keepalive": 60,
            },
            options={},
            source="user",
            entry_id="entry1",
            unique_id="unique_id_1",
            discovery_keys={},
            subentries_data={},
        )

        entry2 = ConfigEntry(
            version=1,
            minor_version=1,
            domain=DOMAIN,
            title="Test Eway Inverter 2",
            data={
                "mqtt_host": "test2.mqtt.broker",
                "mqtt_port": 1883,
                "mqtt_username": "test_user2",
                "mqtt_password": "test_password2",
                "device_id": "device2",
                "device_sn": "sn2",
                "device_model": "model2",
                "scan_interval": 60,
                "keepalive": 120,
            },
            options={},
            source="user",
            entry_id="entry2",
            unique_id="unique_id_2",
            discovery_keys={},
            subentries_data={},
        )

        with patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
        ):
            # Set up both entries
            result1 = await async_setup_entry(hass, entry1)
            result2 = await async_setup_entry(hass, entry2)

            assert result1 is True
            assert result2 is True
            assert len(hass.data[DOMAIN]) == 2
            assert "entry1" in hass.data[DOMAIN]
            assert "entry2" in hass.data[DOMAIN]

            # Verify both coordinators are different instances
            coordinator1 = hass.data[DOMAIN]["entry1"]
            coordinator2 = hass.data[DOMAIN]["entry2"]
            assert coordinator1 != coordinator2
            assert coordinator1.device_id == "device1"
            assert coordinator2.device_id == "device2"
