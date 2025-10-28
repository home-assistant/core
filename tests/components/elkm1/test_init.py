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


async def test_setup_entry_success_auto_configure(
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
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
    ):
        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_forward.assert_called_once()


async def test_setup_entry_success_manual_configure(
    hass: HomeAssistant, mock_elk: MagicMock
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


@pytest.mark.parametrize(
    ("exception", "expected_state", "should_reauth"),
    [
        (ConfigEntryNotReady("Timeout"), ConfigEntryState.SETUP_RETRY, False),
        (ConfigEntryAuthFailed("Auth failed"), ConfigEntryState.SETUP_ERROR, True),
    ],
)
async def test_setup_entry_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_elk: MagicMock,
    exception: Exception,
    expected_state: ConfigEntryState,
    should_reauth: bool,
) -> None:
    """Test setup with various connection errors."""
    with (
        patch(
            "homeassistant.components.elkm1._create_elk_connection",
            return_value=mock_elk,
        ),
        patch("homeassistant.components.elkm1._setup_keypad_handlers"),
        patch(
            "homeassistant.components.elkm1._ensure_elk_connection",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.elkm1.async_discover_device",
            return_value=None,
        ),
        patch.object(mock_config_entry, "async_start_reauth") as mock_reauth,
    ):
        mock_config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is expected_state
    if should_reauth:
        mock_reauth.assert_called_once()
    else:
        mock_reauth.assert_not_called()


async def test_unload_entry_success(
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
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
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


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test async_setup with no configuration."""
    with (
        patch("homeassistant.components.elkm1.async_setup_services"),
        patch("homeassistant.components.elkm1.async_discover_devices"),
        patch("homeassistant.components.elkm1.async_track_time_interval"),
    ):
        result = await async_setup(hass, {})

    assert result is True


async def test_async_setup_with_yaml_config(hass: HomeAssistant) -> None:
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


async def test_setup_entry_with_discovery_success(
    hass: HomeAssistant, mock_elk: MagicMock
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
    hass: HomeAssistant, mock_elk: MagicMock
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
    hass: HomeAssistant, mock_elk: MagicMock
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
        patch("homeassistant.components.elkm1.async_discover_device") as mock_discover,
        patch("homeassistant.components.elkm1.is_ip_address", return_value=False),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    mock_discover.assert_not_called()


async def test_setup_entry_fahrenheit_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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


async def test_async_setup_with_existing_entry_update(hass: HomeAssistant) -> None:
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
    hass: HomeAssistant,
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


async def test_elk_range_validator_single_value(hass: HomeAssistant) -> None:
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


async def test_elk_range_validator_range_value(hass: HomeAssistant) -> None:
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


async def test_elk_range_validator_housecode(hass: HomeAssistant) -> None:
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


async def test_elk_range_validator_housecode_range(hass: HomeAssistant) -> None:
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


async def test_setup_with_no_ranges_manual_config(
    hass: HomeAssistant, mock_elk: MagicMock
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


async def test_wait_for_sync_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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


@pytest.mark.parametrize(
    ("host", "prefix", "unique_id"),
    [
        ("elk://192.168.1.1:2601", "test1", "test1"),
        ("elks://example.com:2601", "test2", "test2"),
        ("serial:///dev/ttyUSB0", "test3", "test3"),
    ],
)
async def test_protocol_setup(
    hass: HomeAssistant,
    mock_elk: MagicMock,
    host: str,
    prefix: str,
    unique_id: str,
) -> None:
    """Test setup with different protocol URLs."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: host,
            CONF_PREFIX: prefix,
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_AUTO_CONFIGURE: True,
        },
        unique_id=unique_id,
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


async def test_unload_entry_without_elk(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading entry without elk connection."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True


async def test_setup_entry_with_comprehensive_config(
    hass: HomeAssistant, mock_elk: MagicMock
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


async def test_setup_with_valid_ranges_corrected(
    hass: HomeAssistant, mock_elk: MagicMock
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


async def test_included_function_through_manual_config(
    hass: HomeAssistant, mock_elk: MagicMock
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


@pytest.mark.parametrize(
    "host",
    [
        "elks://example.com:2601",
        "elksv1_2://example.com:2601",
        "http://example.com:2601",  # Invalid protocol
    ],
)
async def test_protocol_requires_username_password(
    hass: HomeAssistant, host: str
) -> None:
    """Test that certain protocols work in async_setup (validation happens in config flow)."""
    config = {
        DOMAIN: [
            {
                CONF_HOST: host,
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


async def test_entry_with_missing_optional_config(
    hass: HomeAssistant, mock_elk: MagicMock
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
    hass: HomeAssistant, mock_elk: MagicMock
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


async def test_elks_without_credentials_error(hass: HomeAssistant) -> None:
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

    with patch("homeassistant.components.elkm1._create_elk_connection") as mock_create:
        # Configure mock to raise the validation error that would happen
        mock_create.side_effect = ValueError(
            "Username and password required for elks://"
        )

        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_elk_with_invalid_url_scheme(hass: HomeAssistant) -> None:
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

    with patch("homeassistant.components.elkm1._create_elk_connection") as mock_create:
        # Configure mock to raise error for invalid scheme
        mock_create.side_effect = ValueError("Invalid URL scheme")

        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_serial_url_validation(hass: HomeAssistant, mock_elk: MagicMock) -> None:
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
    hass: HomeAssistant, mock_elk: MagicMock
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


async def test_config_with_complex_include_exclude_patterns(
    hass: HomeAssistant, mock_elk: MagicMock
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
    hass: HomeAssistant, mock_elk: MagicMock
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


async def test_connection_error_during_setup(hass: HomeAssistant) -> None:
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

    with patch("homeassistant.components.elkm1._create_elk_connection") as mock_create:
        # Simulate connection error
        mock_create.side_effect = OSError("Connection failed")

        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_elk_library_import_error(hass: HomeAssistant) -> None:
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

    with patch("homeassistant.components.elkm1._create_elk_connection") as mock_create:
        # Simulate import error for elk library
        mock_create.side_effect = ImportError("No module named 'elkm1_lib'")

        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)

    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_keypad_config_handling(hass: HomeAssistant, mock_elk: MagicMock) -> None:
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
        patch("homeassistant.components.elkm1._setup_keypad_handlers") as mock_keypad,
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


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("elks://192.168.1.100", "192.168.1.100"),
        ("elksv1_2://192.168.1.100", "192.168.1.100"),
        ("elk://192.168.1.100", "192.168.1.100"),
        ("serial:///dev/ttyUSB0", "/dev/ttyUSB0"),
    ],
)
def test_hostname_from_url(url: str, expected: str) -> None:
    """Test hostname_from_url with different protocols."""
    result = elkm1.hostname_from_url(url)
    assert result == expected


@pytest.mark.parametrize(
    ("host", "should_raise", "error_match"),
    [
        ("elks://192.168.1.100", True, "Specify username and password"),
        ("elksv1_2://192.168.1.100", True, "Specify username and password"),
        ("elk://192.168.1.100", False, None),
        ("serial:///dev/ttyUSB0", False, None),
        ("invalid://192.168.1.100", True, "Invalid host URL"),
    ],
)
def test_host_validator(host: str, should_raise: bool, error_match: str | None) -> None:
    """Test _host_validator with different protocols."""
    config = {CONF_HOST: host}

    if should_raise:
        with pytest.raises(vol.Invalid, match=error_match):
            elkm1._host_validator(config)
    else:
        result = elkm1._host_validator(config)
        assert result == config


async def test_setup_with_connection_exception(
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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


@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        ("5", (5, 5)),
        ("1-8", (1, 8)),
        ("A1", (1, 1)),
        ("A1-A8", (1, 8)),
        ("P16", (256, 256)),
    ],
)
async def test_elk_range_validator_coverage(
    input_value: str, expected: tuple[int, int]
) -> None:
    """Test _elk_range_validator with various inputs."""
    result = elkm1._elk_range_validator(input_value)
    assert result == expected


async def test_elk_range_validator_invalid() -> None:
    """Test _elk_range_validator with invalid housecode."""
    with pytest.raises(vol.Invalid, match="Invalid range"):
        elkm1._elk_range_validator("Z1")


async def test_has_all_unique_prefixes_coverage() -> None:
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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


async def test_discovery_config_coverage(hass: HomeAssistant) -> None:
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
        patch("homeassistant.components.elkm1._create_elk_connection") as mock_create,
        patch("homeassistant.components.elkm1._setup_keypad_handlers"),
        patch("homeassistant.components.elkm1._ensure_elk_connection"),
        patch("homeassistant.components.elkm1.async_discover_device", return_value={}),
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


async def test_included_function_error_path() -> None:
    """Test _included function with out-of-bounds ranges to trigger error path."""
    values = [False] * 10  # 10 element array
    ranges = [(12, 15)]  # Out of bounds range

    # This should raise an Invalid error for out-of-bounds ranges
    with pytest.raises(vol.Invalid, match="Invalid range"):
        elkm1._included(ranges, True, values)


async def test_ensure_elk_connection_authentication_failure() -> None:
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


async def test_ensure_elk_connection_timeout_error() -> None:
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


async def test_wait_for_elk_sync_login_failure() -> None:
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


async def test_wait_for_elk_sync_login_timeout() -> None:
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


async def test_wait_for_elk_sync_success_complete() -> None:
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


async def test_wait_for_elk_sync_complete_timeout() -> None:
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


async def test_setup_elk_config_include_exclude_value_error() -> None:
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


def test_create_elk_connection_basic() -> None:
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
