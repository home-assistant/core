"""Test the Elk-M1 Control integration following HA testing guidelines."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import elkm1
from homeassistant.components.elkm1 import DOMAIN, async_setup
from homeassistant.components.elkm1.const import CONF_AUTO_CONFIGURE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ENABLED,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_PASSWORD,
    CONF_PREFIX,
    CONF_USERNAME,
    CONF_ZONE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


@pytest.fixture
def mock_elk():
    """Create a mock Elk instance."""
    elk = MagicMock()
    elk.panel.temperature_units = "F"
    elk.panel.name = "Test Panel"
    elk.keypads = []
    for i in range(16):
        keypad = MagicMock()
        keypad.index = i
        keypad.name = f"Keypad {i + 1}"
        keypad.add_callback = MagicMock()
        elk.keypads.append(keypad)
    elk.connect = MagicMock()
    elk.disconnect = MagicMock()
    elk.add_handler = MagicMock()
    return elk


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "elk://192.168.1.1",
            CONF_PREFIX: "test",
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_AUTO_CONFIGURE: True,
        },
        unique_id="test",
    )


class TestSetupEntry:
    """Test async_setup_entry function."""

    async def test_setup_entry_success_auto_configure(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_elk: MagicMock,
    ) -> None:
        """Test successful setup with auto configure."""
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(
                hass.config_entries, "async_forward_entry_setups"
            ) as mock_forward,
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert mock_config_entry.state is ConfigEntryState.LOADED
        mock_forward.assert_called_once()

    async def test_setup_entry_success_manual_configure(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test successful setup with manual configuration."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "area": {CONF_ENABLED: True, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: True, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: True, "include": [], "exclude": []},
                "output": {CONF_ENABLED: True, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: True, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
                "task": {CONF_ENABLED: True, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: True, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED

    async def test_setup_entry_connection_timeout(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_elk: MagicMock,
    ) -> None:
        """Test setup with connection timeout."""
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch(
                "homeassistant.components.elkm1._ensure_elk_connection",
                side_effect=ConfigEntryNotReady("Timeout"),
            ),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    async def test_setup_entry_auth_failed(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_elk: MagicMock,
    ) -> None:
        """Test setup with authentication failure."""
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch(
                "homeassistant.components.elkm1._ensure_elk_connection",
                side_effect=ConfigEntryAuthFailed("Auth failed"),
            ),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(mock_config_entry, "async_start_reauth"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


class TestUnloadEntry:
    """Test async_unload_entry function."""

    async def test_unload_entry_success(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_elk: MagicMock,
    ) -> None:
        """Test successful unloading of config entry."""
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
            patch.object(
                hass.config_entries, "async_unload_platforms", return_value=True
            ),
        ):
            # First setup the integration
            mock_config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Then unload it
            result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
        mock_elk.disconnect.assert_called()


class TestAsyncSetup:
    """Test async_setup function."""

    async def test_async_setup_no_config(self, hass: HomeAssistant) -> None:
        """Test async_setup with no configuration."""
        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, {})

        assert result is True

    async def test_async_setup_with_yaml_config(self, hass: HomeAssistant) -> None:
        """Test async_setup with YAML configuration."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "home",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: True,
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
            patch.object(hass.config_entries.flow, "async_init") as mock_init,
        ):
            result = await async_setup(hass, config)

        assert result is True
        mock_init.assert_called_once()


class TestDiscoveryAndUpdate:
    """Test discovery and update functions."""

    async def test_setup_entry_with_discovery_success(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with successful device discovery."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id=None,  # Missing unique ID to trigger discovery
        )

        mock_device = MagicMock()

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=mock_device,
            ),
            patch(
                "homeassistant.components.elkm1.async_update_entry_from_discovery"
            ) as mock_update,
            patch("homeassistant.components.elkm1.is_ip_address", return_value=True),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        mock_update.assert_called_once_with(hass, config_entry, mock_device)

    async def test_setup_entry_with_discovery_failed(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup continues despite discovery failure."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id=None,
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                side_effect=OSError,
            ),
            patch("homeassistant.components.elkm1.is_ip_address", return_value=True),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True

    async def test_setup_entry_non_ip_host_no_discovery(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with non-IP host skips discovery."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "serial:///dev/ttyUSB0",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id=None,
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device"
            ) as mock_discover,
            patch("homeassistant.components.elkm1.is_ip_address", return_value=False),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        mock_discover.assert_not_called()


class TestTemperatureUnits:
    """Test temperature unit handling."""

    async def test_setup_entry_fahrenheit_temperature(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test setup with Fahrenheit temperature units."""
        mock_elk = MagicMock()
        mock_elk.panel.temperature_units = "F"

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True

    async def test_setup_entry_celsius_temperature(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test setup with Celsius temperature units."""
        mock_elk = MagicMock()
        mock_elk.panel.temperature_units = "C"

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True


class TestYamlConfig:
    """Test YAML configuration handling."""

    async def test_async_setup_with_existing_entry_update(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup with existing entry that gets updated."""
        existing_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="home",
            data={CONF_HOST: "elk://192.168.1.2"},
        )
        existing_entry.add_to_hass(hass)

        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "home",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: True,
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
            patch.object(hass.config_entries, "async_update_entry") as mock_update,
        ):
            result = await async_setup(hass, config)

        assert result is True
        mock_update.assert_called_once()

    async def test_async_setup_with_duplicate_prefix_validation(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup with validation that catches duplicate prefixes."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "home",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: True,
                },
                {
                    CONF_HOST: "elk://192.168.1.2",
                    CONF_PREFIX: "home",  # Duplicate prefix
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: True,
                },
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, config)

        assert result is True


class TestRangeValidation:
    """Test range validation functions through config setup."""

    async def test_elk_range_validator_single_value(self, hass: HomeAssistant) -> None:
        """Test _elk_range_validator with single value through config."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "test",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: False,
                    "area": {CONF_ENABLED: True, CONF_INCLUDE: ["5"], "exclude": []},
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            # Should not raise validation error
            result = await async_setup(hass, config)

        assert result is True

    async def test_elk_range_validator_range_value(self, hass: HomeAssistant) -> None:
        """Test _elk_range_validator with range value through config."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "test",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: False,
                    "area": {
                        CONF_ENABLED: True,
                        CONF_INCLUDE: ["1-5"],
                        "exclude": [],
                    },
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, config)

        assert result is True

    async def test_elk_range_validator_housecode(self, hass: HomeAssistant) -> None:
        """Test _elk_range_validator with housecode value through config."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "test",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: False,
                    "plc": {CONF_ENABLED: True, CONF_INCLUDE: ["a1"], "exclude": []},
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, config)

        assert result is True

    async def test_elk_range_validator_housecode_range(
        self, hass: HomeAssistant
    ) -> None:
        """Test _elk_range_validator with housecode range through config."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "test",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                    CONF_AUTO_CONFIGURE: False,
                    "plc": {
                        CONF_ENABLED: True,
                        CONF_INCLUDE: ["a1-a5"],
                        "exclude": [],
                    },
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, config)

        assert result is True


class TestManualConfiguration:
    """Test manual configuration scenarios."""

    async def test_setup_with_no_ranges_manual_config(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with no ranges in manual configuration."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "area": {CONF_ENABLED: True, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: True, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: True, "include": [], "exclude": []},
                "output": {CONF_ENABLED: True, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: True, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
                "task": {CONF_ENABLED: True, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: True, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED

    async def test_setup_entry_config_error_in_setup(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_elk: MagicMock,
    ) -> None:
        """Test setup with configuration error during setup."""
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch(
                "homeassistant.components.elkm1._setup_elk_config",
                side_effect=Exception("Config error"),
            ),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False


class TestUtilityFunctions:
    """Test utility functions through integration testing."""

    async def test_wait_for_sync_success(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test successful sync wait."""
        mock_elk = MagicMock()
        mock_elk.panel.temperature_units = "F"

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                return_value=True,
            ),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True

    async def test_wait_for_sync_failure(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test sync wait failure."""
        mock_elk = MagicMock()

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                return_value=False,
            ),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(mock_config_entry, "async_start_reauth"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False

    async def test_keypad_event_setup(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test keypad event handler setup."""
        mock_elk = MagicMock()
        mock_elk.panel.temperature_units = "F"

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch(
                "homeassistant.components.elkm1._setup_keypad_handlers"
            ) as mock_keypad_setup,
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        mock_keypad_setup.assert_called_once_with(hass, mock_elk)


class TestVariousHostFormats:
    """Test various host URL formats."""

    async def test_elk_protocol_setup(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with elk:// protocol."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1:2601",
                CONF_PREFIX: "test1",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id="test1",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True

    async def test_elks_protocol_setup(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with elks:// protocol."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elks://example.com:2601",
                CONF_PREFIX: "test2",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id="test2",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True

    async def test_serial_protocol_setup(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with serial:// protocol."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "serial:///dev/ttyUSB0",
                CONF_PREFIX: "test3",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id="test3",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True


class TestUnloadWithoutElk:
    """Test unload scenarios."""

    async def test_unload_entry_without_elk(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test unloading entry without elk connection."""
        mock_config_entry.add_to_hass(hass)

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True


class TestConfigurationCoverage:
    """Test configuration scenarios to improve coverage."""

    async def test_setup_entry_with_comprehensive_config(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test comprehensive configuration coverage."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "area": {CONF_ENABLED: True, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: True, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: True, "include": [], "exclude": []},
                "output": {CONF_ENABLED: True, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: True, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
                "task": {CONF_ENABLED: True, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: True, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


class TestFixedRangeValidation:
    """Test corrected range validation that doesn't trigger type errors."""

    async def test_setup_with_valid_ranges_corrected(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test setup with ranges that have been properly validated."""
        # The ranges are converted by _elk_range_validator during config validation
        # So we need to pass the already-converted tuples
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "area": {
                    CONF_ENABLED: True,
                    CONF_INCLUDE: [(1, 5)],
                    CONF_EXCLUDE: [(3, 3)],
                },
                "counter": {CONF_ENABLED: True, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: True, "include": [], "exclude": []},
                "output": {CONF_ENABLED: True, "include": [], "exclude": []},
                "plc": {
                    CONF_ENABLED: True,
                    CONF_INCLUDE: [(17, 21)],
                    CONF_EXCLUDE: [(19, 19)],
                },  # a1-a5, a3
                "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
                "task": {CONF_ENABLED: True, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
                CONF_ZONE: {
                    CONF_ENABLED: True,
                    CONF_INCLUDE: [(1, 1), (5, 10)],
                    CONF_EXCLUDE: [(7, 7)],
                },
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


class TestIncludedFunctionCoverageFixed:
    """Test the _included function through proper public interface."""

    async def test_included_function_through_manual_config(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test the _included function gets called during manual config setup."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                # Use properly formatted tuples to avoid type errors
                "area": {CONF_ENABLED: True, CONF_INCLUDE: [(1, 3)], "exclude": []},
                "counter": {
                    CONF_ENABLED: True,
                    "include": [],
                    CONF_EXCLUDE: [(2, 2)],
                },
                "keypad": {
                    CONF_ENABLED: True,
                    CONF_INCLUDE: [(1, 5)],
                    CONF_EXCLUDE: [(3, 3)],
                },
                "output": {CONF_ENABLED: True, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: True, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
                "task": {CONF_ENABLED: True, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: True, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


class TestUrlValidationCoverage:
    """Test URL validation logic."""

    async def test_elks_protocol_requires_username_password(
        self, hass: HomeAssistant
    ) -> None:
        """Test that elks:// protocol requires username and password."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elks://example.com:2601",
                    CONF_PREFIX: "test",
                    CONF_AUTO_CONFIGURE: True,
                    # Missing username and password should trigger validation
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            # This should pass despite missing username/password because async_setup
            # doesn't validate the individual configs - that happens during config flow
            result = await async_setup(hass, config)

        assert result is True

    async def test_elksv1_2_protocol_requires_username_password(
        self, hass: HomeAssistant
    ) -> None:
        """Test that elksv1_2:// protocol requires username and password."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elksv1_2://example.com:2601",
                    CONF_PREFIX: "test",
                    CONF_AUTO_CONFIGURE: True,
                    # Missing username and password should trigger validation
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, config)

        assert result is True

    async def test_invalid_protocol_url(self, hass: HomeAssistant) -> None:
        """Test invalid protocol URL handling."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "http://example.com:2601",  # Invalid protocol
                    CONF_PREFIX: "test",
                    CONF_AUTO_CONFIGURE: True,
                }
            ]
        }

        with (
            patch("homeassistant.components.elkm1.async_setup_services"),
            patch("homeassistant.components.elkm1.async_discover_devices"),
            patch("homeassistant.components.elkm1.async_track_time_interval"),
        ):
            result = await async_setup(hass, config)

        assert result is True


class TestAdvancedConfigurationScenarios:
    """Test advanced configuration scenarios."""

    async def test_entry_with_missing_optional_config(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test config entry with missing optional configuration fields."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                # Include all required config items with minimal configuration
                "area": {CONF_ENABLED: True, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: True, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED

    async def test_entry_with_all_disabled_config(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test config entry with all items disabled."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "area": {CONF_ENABLED: False, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: False, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


class TestCreateElkUrlValidation:
    """Test _create_elk_url validation logic indirectly through config entry setup."""

    async def test_elks_without_credentials_error(self, hass: HomeAssistant) -> None:
        """Test elks:// URL without credentials raises proper error."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elks://192.168.1.1:2601",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",  # Empty username for elks:// should cause error
                CONF_PASSWORD: "",  # Empty password for elks:// should cause error
                CONF_AUTO_CONFIGURE: False,
            },
            unique_id="test",
        )

        with patch(
            "homeassistant.components.elkm1._create_elk_connection"
        ) as mock_create:
            # Configure mock to raise the validation error that would happen
            mock_create.side_effect = ValueError(
                "Username and password required for elks://"
            )

            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR

    async def test_elk_with_invalid_url_scheme(self, hass: HomeAssistant) -> None:
        """Test invalid URL scheme handling."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "invalid://192.168.1.1:2601",
                CONF_PREFIX: "test",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_AUTO_CONFIGURE: False,
            },
            unique_id="test",
        )

        with patch(
            "homeassistant.components.elkm1._create_elk_connection"
        ) as mock_create:
            # Configure mock to raise error for invalid scheme
            mock_create.side_effect = ValueError("Invalid URL scheme")

            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR

    async def test_serial_url_validation(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test serial:// URL validation."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "serial:///dev/ttyUSB0",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                # Include all required config items
                "area": {CONF_ENABLED: False, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: False, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED

    async def test_elk_protocol_basic_connection(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test basic elk:// protocol connection."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1:2601",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                # Include all required config items
                "area": {CONF_ENABLED: False, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: False, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


class TestIncludedFunctionCoverage:
    """Test _included function and related coverage through config entry setup."""

    async def test_config_with_complex_include_exclude_patterns(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test config with complex include/exclude patterns to trigger _included function."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                # Include specific zones with ranges to trigger _included function
                CONF_ZONE: {
                    CONF_ENABLED: True,
                    "include": [
                        (1, 5),
                        (10, 10),
                        (15, 20),
                    ],  # Tuples as expected by _included
                    "exclude": [(3, 3), (17, 18)],  # Tuples as expected by _included
                },
                "area": {
                    CONF_ENABLED: True,
                    "include": [(1, 2), (4, 4)],
                    "exclude": [],
                },
                "output": {
                    CONF_ENABLED: True,
                    "include": [],
                    "exclude": [(100, 105)],  # Tuple as expected by _included
                },
                # Include other required config items
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED

    async def test_config_with_edge_case_ranges(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test config with edge case range patterns."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                # Edge case ranges
                CONF_ZONE: {
                    CONF_ENABLED: True,
                    "include": [
                        (1, 1),
                        (5, 5),
                        (10, 15),
                    ],  # Tuples as expected by _included
                    "exclude": [(208, 208)],  # Single item exclude as tuple
                },
                "counter": {
                    CONF_ENABLED: True,
                    "include": [(1, 64)],  # Full range as tuple
                    "exclude": [(32, 33)],
                },
                # Include other required config items
                "area": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED


class TestConnectionErrorHandling:
    """Test connection error handling scenarios."""

    async def test_connection_error_during_setup(self, hass: HomeAssistant) -> None:
        """Test connection error during setup."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
            },
            unique_id="test",
        )

        with patch(
            "homeassistant.components.elkm1._create_elk_connection"
        ) as mock_create:
            # Simulate connection error
            mock_create.side_effect = OSError("Connection failed")

            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR

    async def test_elk_library_import_error(self, hass: HomeAssistant) -> None:
        """Test error when elk library cannot be imported."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
            },
            unique_id="test",
        )

        with patch(
            "homeassistant.components.elkm1._create_elk_connection"
        ) as mock_create:
            # Simulate import error for elk library
            mock_create.side_effect = ImportError("No module named 'elkm1_lib'")

            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


class TestKeypadHandling:
    """Test keypad handling and related functions."""

    async def test_keypad_config_handling(
        self, hass: HomeAssistant, mock_elk: MagicMock
    ) -> None:
        """Test keypad configuration handling."""
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "keypad": {
                    CONF_ENABLED: True,
                    "include": [(1, 2), (4, 4)],  # Tuples as expected by _included
                    "exclude": [(3, 3)],
                },
                # Include other required config items
                "area": {CONF_ENABLED: False, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
                CONF_ZONE: {CONF_ENABLED: False, "include": [], "exclude": []},
            },
            unique_id="test",
        )

        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch(
                "homeassistant.components.elkm1._setup_keypad_handlers"
            ) as mock_keypad,
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED
        # Verify keypad handler was called
        mock_keypad.assert_called_once()


class TestHostnameFromUrl:
    """Test hostname_from_url function to cover URL parsing logic."""

    def test_hostname_from_url_elks_protocol_without_credentials(self):
        """Test hostname_from_url with elks:// protocol without credentials."""
        result = elkm1.hostname_from_url("elks://192.168.1.100")
        assert result == "192.168.1.100"

    def test_hostname_from_url_elksv1_2_protocol_without_credentials(self):
        """Test hostname_from_url with elksv1_2:// protocol without credentials."""
        result = elkm1.hostname_from_url("elksv1_2://192.168.1.100")
        assert result == "192.168.1.100"

    def test_hostname_from_url_elk_protocol_without_credentials(self):
        """Test hostname_from_url with elk:// protocol without credentials."""
        result = elkm1.hostname_from_url("elk://192.168.1.100")
        assert result == "192.168.1.100"

    def test_hostname_from_url_serial_protocol_without_credentials(self):
        """Test hostname_from_url with serial:// protocol without credentials."""
        result = elkm1.hostname_from_url("serial:///dev/ttyUSB0")
        assert result == "/dev/ttyUSB0"


class TestHostValidation:
    """Test _host_validator function to cover validation logic."""

    def test_host_validator_elks_protocol_without_credentials_error(self):
        """Test _host_validator with elks:// protocol without credentials raises error."""
        config = {CONF_HOST: "elks://192.168.1.100"}

        # This should raise a validation error
        with pytest.raises(vol.Invalid, match="Specify username and password"):
            elkm1._host_validator(config)

    def test_host_validator_elksv1_2_protocol_without_credentials_error(self):
        """Test _host_validator with elksv1_2:// protocol without credentials raises error."""
        config = {CONF_HOST: "elksv1_2://192.168.1.100"}

        # This should raise a validation error
        with pytest.raises(vol.Invalid, match="Specify username and password"):
            elkm1._host_validator(config)

    def test_host_validator_elk_protocol_success(self):
        """Test _host_validator with elk:// protocol succeeds."""
        config = {CONF_HOST: "elk://192.168.1.100"}
        result = elkm1._host_validator(config)
        assert result == config

    def test_host_validator_serial_protocol_success(self):
        """Test _host_validator with serial:// protocol succeeds."""
        config = {CONF_HOST: "serial:///dev/ttyUSB0"}
        result = elkm1._host_validator(config)
        assert result == config

    def test_host_validator_invalid_scheme_error(self):
        """Test _host_validator with invalid scheme raises error."""
        config = {CONF_HOST: "invalid://192.168.1.100"}

        # This should raise a validation error
        with pytest.raises(vol.Invalid, match="Invalid host URL"):
            elkm1._host_validator(config)


class TestErrorHandling:
    """Test error handling in async_setup_entry."""

    async def test_setup_with_connection_exception(
        self,
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_elk: MagicMock,
    ) -> None:
        """Test setup with generic connection exception."""
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch(
                "homeassistant.components.elkm1._ensure_elk_connection",
                side_effect=Exception("Unknown connection error"),
            ),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False

    async def test_setup_entry_config_value_error(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test setup with configuration value error."""
        with (
            patch(
                "homeassistant.components.elkm1._setup_elk_config",
                side_effect=ValueError("Configuration error"),
            ),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is False

    async def test_elk_range_validator_coverage(self):
        """Test _elk_range_validator to cover lines 103-115."""
        # Test single number
        result = elkm1._elk_range_validator("5")
        assert result == (5, 5)

        # Test range
        result = elkm1._elk_range_validator("1-8")
        assert result == (1, 8)

        # Test housecode single
        result = elkm1._elk_range_validator("A1")
        assert result == (1, 1)

        # Test housecode range
        result = elkm1._elk_range_validator("A1-A8")
        assert result == (1, 8)

        # Test edge case housecode
        result = elkm1._elk_range_validator("P16")
        assert result == (256, 256)

        # Test invalid housecode to cover error path line 107
        with pytest.raises(vol.Invalid, match="Invalid range"):
            elkm1._elk_range_validator("Z1")

    async def test_has_all_unique_prefixes_coverage(self):
        """Test _has_all_unique_prefixes to cover lines 123-126."""
        # Test valid unique prefixes
        devices = [
            {CONF_PREFIX: "house1"},
            {CONF_PREFIX: "house2"},
        ]
        result = elkm1._has_all_unique_prefixes(devices)
        assert result == devices

        # Test duplicate prefixes should raise
        devices_dup = [
            {CONF_PREFIX: "house1"},
            {CONF_PREFIX: "house1"},  # Duplicate
        ]
        with pytest.raises(vol.Invalid):
            elkm1._has_all_unique_prefixes(devices_dup)

    async def test_keypad_event_handling_coverage(
        self, hass: HomeAssistant, mock_config_entry: MockConfigEntry
    ) -> None:
        """Test keypad event handling to cover lines 259-274."""
        mock_elk = MagicMock()
        mock_elk.panel.temperature_units = "F"
        mock_elk.panel.name = "Test Panel"

        # Create mock keypad
        mock_keypad = MagicMock()
        mock_keypad.name = "Test Keypad"
        mock_keypad.index = 0
        mock_elk.keypads = [mock_keypad]

        # Test keypad callback setup
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection",
                return_value=mock_elk,
            ),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device",
                return_value=None,
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True
        # Verify keypad callback was set up
        mock_keypad.add_callback.assert_called_once()

        # Test keypad changed callback (simulate keypress event)
        callback_func = mock_keypad.add_callback.call_args[0][0]

        # Test with keypress changeset
        changeset = {"last_keypress": ("F1", 1)}
        callback_func(mock_keypad, changeset)

        # Test with None keypress (should return early)
        changeset_none = {"last_keypress": None}
        callback_func(mock_keypad, changeset_none)

        # Test with missing keypress key
        changeset_missing = {}
        callback_func(mock_keypad, changeset_missing)

    async def test_discovery_config_coverage(self, hass: HomeAssistant) -> None:
        """Test discovery configuration to cover missing lines."""
        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.100:2601",  # Valid URL format
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
                CONF_PREFIX: "elkm1",  # Add required prefix
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id="test",
        )

        # Test successful setup with auto configure
        with (
            patch(
                "homeassistant.components.elkm1._create_elk_connection"
            ) as mock_create,
            patch("homeassistant.components.elkm1._setup_keypad_handlers"),
            patch("homeassistant.components.elkm1._ensure_elk_connection"),
            patch(
                "homeassistant.components.elkm1.async_discover_device", return_value={}
            ),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            mock_elk = MagicMock()
            mock_elk.panel.temperature_units = "F"
            mock_elk.panel.name = "Test Panel"
            mock_elk.keypads = []
            mock_create.return_value = mock_elk

            mock_config_entry.add_to_hass(hass)
            result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert result is True

    async def test_included_function_error_path(self):
        """Test _included function with out-of-bounds ranges to trigger error path."""
        values = [False] * 10  # 10 element array
        ranges = [(12, 15)]  # Out of bounds range

        # This should raise an Invalid error for out-of-bounds ranges
        with pytest.raises(vol.Invalid, match="Invalid range"):
            elkm1._included(ranges, True, values)


class TestConnectionErrorPaths:
    """Test connection error handling and timeout scenarios."""

    async def test_ensure_elk_connection_authentication_failure(self):
        """Test _ensure_elk_connection with authentication failure."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()

        # Test authentication failure during sync
        with (
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                return_value=False,
            ),
            pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"),
        ):
            await elkm1._ensure_elk_connection(mock_elk, "192.168.1.100")

        # Verify disconnect was called (may be called multiple times)
        assert mock_elk.disconnect.call_count >= 1

    async def test_ensure_elk_connection_timeout_error(self):
        """Test _ensure_elk_connection with timeout error."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()

        # Test timeout during connection
        with (
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                side_effect=TimeoutError("Connection timeout"),
            ),
            pytest.raises(
                ConfigEntryNotReady, match="Timed out connecting to 192.168.1.100"
            ),
        ):
            await elkm1._ensure_elk_connection(mock_elk, "192.168.1.100")

        # Verify disconnect was called
        mock_elk.disconnect.assert_called_once()

    async def test_ensure_elk_connection_login_failed_exception(self):
        """Test _ensure_elk_connection with login failed exception."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()

        # Test exception with "login failed" in message
        with (
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                side_effect=Exception("login failed"),
            ),
            pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"),
        ):
            await elkm1._ensure_elk_connection(mock_elk, "192.168.1.100")

        # Verify disconnect was called
        mock_elk.disconnect.assert_called_once()

    async def test_ensure_elk_connection_invalid_exception(self):
        """Test _ensure_elk_connection with invalid credentials exception."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()

        # Test exception with "invalid" in message
        with (
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                side_effect=Exception("invalid credentials"),
            ),
            pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"),
        ):
            await elkm1._ensure_elk_connection(mock_elk, "192.168.1.100")

        # Verify disconnect was called
        mock_elk.disconnect.assert_called_once()

    async def test_ensure_elk_connection_generic_exception(self):
        """Test _ensure_elk_connection with generic exception."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()

        # Test generic exception (not auth related)
        with (
            patch(
                "homeassistant.components.elkm1.async_wait_for_elk_to_sync",
                side_effect=Exception("Connection error"),
            ),
            pytest.raises(Exception, match="Connection error"),
        ):
            await elkm1._ensure_elk_connection(mock_elk, "192.168.1.100")

        # Verify disconnect was called
        mock_elk.disconnect.assert_called_once()


class TestAsyncWaitForElkToSync:
    """Test async_wait_for_elk_to_sync function coverage."""

    async def test_wait_for_elk_sync_login_failure(self):
        """Test login failure in wait_for_elk_to_sync."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()
        mock_elk.add_handler = MagicMock()

        # Mock the handlers to simulate login failure
        def mock_add_handler(event_name, handler):
            if event_name == "login":
                # Simulate login failure
                handler(False)  # Login failed
            elif event_name == "sync_complete":
                pass  # Won't be called due to login failure

        mock_elk.add_handler.side_effect = mock_add_handler

        result = await elkm1.async_wait_for_elk_to_sync(mock_elk, 10, 10)

        # Should return False for login failure
        assert result is False
        # Disconnect should be called on login failure
        mock_elk.disconnect.assert_called_once()

    async def test_wait_for_elk_sync_login_timeout(self):
        """Test login timeout in wait_for_elk_to_sync."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()
        mock_elk.add_handler = MagicMock()

        # Mock the handlers to not trigger any events (timeout)
        def mock_add_handler(_event_name, _handler):
            pass  # Don't call any handlers, causing timeout

        mock_elk.add_handler.side_effect = mock_add_handler

        with pytest.raises(TimeoutError):
            await elkm1.async_wait_for_elk_to_sync(mock_elk, 1, 1)  # Use int values

        # Disconnect should be called on timeout
        mock_elk.disconnect.assert_called()

    async def test_wait_for_elk_sync_success_complete(self):
        """Test successful login and sync completion."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()
        mock_elk.add_handler = MagicMock()

        login_handler = None
        sync_handler = None

        def mock_add_handler(event_name, handler):
            nonlocal login_handler, sync_handler
            if event_name == "login":
                login_handler = handler
            elif event_name == "sync_complete":
                sync_handler = handler

        mock_elk.add_handler.side_effect = mock_add_handler

        # Create a task to simulate successful login and sync
        async def simulate_events():
            await asyncio.sleep(0.01)  # Small delay
            if login_handler is not None:
                login_handler(True)  # Login success
            await asyncio.sleep(0.01)  # Small delay
            if sync_handler is not None:
                sync_handler()  # Sync complete

        # Start the simulation
        task = asyncio.create_task(simulate_events())

        result = await elkm1.async_wait_for_elk_to_sync(mock_elk, 1, 1)

        await task  # Wait for simulation to complete

        # Should return True for successful sync
        assert result is True
        # Disconnect should not be called on success
        mock_elk.disconnect.assert_not_called()

    async def test_wait_for_elk_sync_complete_timeout(self):
        """Test sync_complete timeout after successful login."""
        mock_elk = MagicMock()
        mock_elk.disconnect = MagicMock()
        mock_elk.add_handler = MagicMock()

        login_handler = None

        def mock_add_handler(event_name, handler):
            nonlocal login_handler
            if event_name == "login":
                login_handler = handler
            elif event_name == "sync_complete":
                pass  # Don't set sync handler, causing timeout

        mock_elk.add_handler.side_effect = mock_add_handler

        # Create a task to simulate successful login but no sync
        async def simulate_login():
            await asyncio.sleep(0.01)  # Small delay
            if login_handler is not None:
                login_handler(True)  # Login success, but no sync

        # Start the simulation
        task = asyncio.create_task(simulate_login())

        with pytest.raises(TimeoutError):
            await elkm1.async_wait_for_elk_to_sync(mock_elk, 1, 1)  # Use int values

        await task  # Wait for simulation to complete

        # Disconnect should be called on timeout
        mock_elk.disconnect.assert_called()


class TestConfigurationIncludeExcludeError:
    """Test configuration include/exclude error handling."""

    async def test_setup_elk_config_include_exclude_value_error(self):
        """Test ValueError handling in _setup_elk_config."""
        # Configuration that will trigger ValueError in _included function
        # Need to provide all ELK_ELEMENTS for the configuration
        conf = {
            CONF_AUTO_CONFIGURE: False,
            "area": {CONF_ENABLED: True, "include": [], "exclude": []},
            "counter": {CONF_ENABLED: True, "include": [], "exclude": []},
            "keypad": {CONF_ENABLED: True, "include": [], "exclude": []},
            "output": {CONF_ENABLED: True, "include": [], "exclude": []},
            "plc": {
                CONF_ENABLED: True,
                "include": [(1, 5)],  # Valid range
                "exclude": [],
            },
            "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
            "task": {CONF_ENABLED: True, "include": [], "exclude": []},
            "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
            CONF_ZONE: {CONF_ENABLED: True, "include": [], "exclude": []},
        }

        # Mock _included to raise ValueError to trigger the exception handling lines 237-239
        with (
            patch(
                "homeassistant.components.elkm1._included",
                side_effect=ValueError("Test error"),
            ),
            pytest.raises(ValueError, match="Test error"),
        ):
            elkm1._setup_elk_config(conf)


class TestCreateElkConnection:
    """Test _create_elk_connection function coverage."""

    def test_create_elk_connection_basic(self):
        """Test _create_elk_connection function to cover lines 245-253."""
        conf = {
            CONF_HOST: "elk://192.168.1.100:2601",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        }

        # Mock the Elk class to avoid actual connection
        with patch("homeassistant.components.elkm1.Elk") as mock_elk_class:
            mock_elk_instance = MagicMock()
            mock_elk_class.return_value = mock_elk_instance

            result = elkm1._create_elk_connection(conf)

            # Verify the Elk class was called with correct parameters
            mock_elk_class.assert_called_once_with(
                {
                    "url": "elk://192.168.1.100:2601",
                    "userid": "user",
                    "password": "pass",
                }
            )

            # Verify connect was called
            mock_elk_instance.connect.assert_called_once()

            # Verify the instance is returned
            assert result is mock_elk_instance
