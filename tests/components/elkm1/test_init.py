"""Test the Elk-M1 Control init module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.elkm1 import (
    DOMAIN,
    _async_find_matching_config_entry,
    _create_elk_connection,
    _elk_range_validator,
    _ensure_elk_connection,
    _has_all_unique_prefixes,
    _host_validator,
    _included,
    _setup_elk_config,
    _setup_keypad_handlers,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    async_wait_for_elk_to_sync,
    hostname_from_url,
)
from homeassistant.components.elkm1.const import (
    CONF_AUTO_CONFIGURE,
    EVENT_ELKM1_KEYPAD_KEY_PRESSED,
)
from homeassistant.const import (
    CONF_ENABLED,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PREFIX,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


class TestUtilityFunctions:
    """Test utility functions."""

    def test_hostname_from_url(self) -> None:
        """Test hostname extraction from URL."""
        assert hostname_from_url("elk://192.168.1.1") == "192.168.1.1"
        assert hostname_from_url("elks://example.com:2601") == "example.com"
        assert hostname_from_url("serial:///dev/ttyS0") == "/dev/ttyS0"

    def test_host_validator_valid_elk_url(self) -> None:
        """Test _host_validator with valid elk:// URL."""
        config = {CONF_HOST: "elk://192.168.1.1"}
        result = _host_validator(config)
        assert result == config

    def test_host_validator_valid_serial_url(self) -> None:
        """Test _host_validator with valid serial:// URL."""
        config = {CONF_HOST: "serial:///dev/ttyS0"}
        result = _host_validator(config)
        assert result == config

    def test_host_validator_secure_with_credentials(self) -> None:
        """Test _host_validator with secure URL and credentials."""
        config = {
            CONF_HOST: "elks://192.168.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        }
        result = _host_validator(config)
        assert result == config

    def test_host_validator_secure_tls12_with_credentials(self) -> None:
        """Test _host_validator with TLS 1.2 URL and credentials."""
        config = {
            CONF_HOST: "elksv1_2://192.168.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        }
        result = _host_validator(config)
        assert result == config

    def test_host_validator_secure_missing_username(self) -> None:
        """Test _host_validator with secure URL missing username."""
        config = {CONF_HOST: "elks://192.168.1.1", CONF_PASSWORD: "pass"}
        with pytest.raises(vol.Invalid, match="Specify username and password"):
            _host_validator(config)

    def test_host_validator_secure_missing_password(self) -> None:
        """Test _host_validator with secure URL missing password."""
        config = {CONF_HOST: "elks://192.168.1.1", CONF_USERNAME: "user"}
        with pytest.raises(vol.Invalid, match="Specify username and password"):
            _host_validator(config)

    def test_host_validator_invalid_url(self) -> None:
        """Test _host_validator with invalid URL."""
        config = {CONF_HOST: "http://192.168.1.1"}
        with pytest.raises(vol.Invalid, match="Invalid host URL"):
            _host_validator(config)


class TestElkRangeValidator:
    """Test Elk range validator functions."""

    def test_elk_range_validator_single_number(self) -> None:
        """Test _elk_range_validator with single number."""
        assert _elk_range_validator("5") == (5, 5)

    def test_elk_range_validator_number_range(self) -> None:
        """Test _elk_range_validator with number range."""
        assert _elk_range_validator("1-10") == (1, 10)

    def test_elk_range_validator_single_housecode(self) -> None:
        """Test _elk_range_validator with single housecode."""
        assert _elk_range_validator("a1") == (1, 1)
        assert _elk_range_validator("p16") == (256, 256)

    def test_elk_range_validator_housecode_range(self) -> None:
        """Test _elk_range_validator with housecode range."""
        assert _elk_range_validator("a1-a5") == (1, 5)
        assert _elk_range_validator("b2-c3") == (18, 35)

    def test_elk_range_validator_invalid_housecode(self) -> None:
        """Test _elk_range_validator with invalid housecode."""
        with pytest.raises(vol.Invalid, match="Invalid range"):
            _elk_range_validator("q1")  # q is not valid (only a-p)

        with pytest.raises(vol.Invalid, match="Invalid range"):
            _elk_range_validator("a17")  # 17 is not valid (only 1-16)

        with pytest.raises(vol.Invalid, match="Invalid range"):
            _elk_range_validator("a0")  # 0 is not valid


class TestPrefixValidator:
    """Test prefix validation functions."""

    def test_has_all_unique_prefixes_valid(self) -> None:
        """Test _has_all_unique_prefixes with unique prefixes."""
        value = [
            {CONF_PREFIX: "home"},
            {CONF_PREFIX: "office"},
            {CONF_PREFIX: ""},
        ]
        result = _has_all_unique_prefixes(value)
        assert result == value

    def test_has_all_unique_prefixes_case_insensitive(self) -> None:
        """Test _has_all_unique_prefixes allows case variations."""
        value = [
            {CONF_PREFIX: "Home"},
            {CONF_PREFIX: "home"},
        ]
        # voluptuous.Unique() is case-sensitive, so this should pass
        result = _has_all_unique_prefixes(value)
        assert result == value

    def test_has_all_unique_prefixes_duplicate(self) -> None:
        """Test _has_all_unique_prefixes with duplicate prefixes."""
        value = [
            {CONF_PREFIX: "home"},
            {CONF_PREFIX: "home"},
        ]
        with pytest.raises(vol.Invalid):
            _has_all_unique_prefixes(value)


class TestSetupElkConfig:
    """Test Elk configuration setup."""

    def test_setup_elk_config_auto_configure(self) -> None:
        """Test _setup_elk_config with auto configure enabled."""
        conf = {CONF_AUTO_CONFIGURE: True}
        result = _setup_elk_config(conf)
        assert result == {}

    def test_setup_elk_config_manual_configure(self) -> None:
        """Test _setup_elk_config with manual configuration."""
        conf = {
            CONF_AUTO_CONFIGURE: False,
            "zone": {CONF_ENABLED: True, "include": [], "exclude": []},
            "area": {CONF_ENABLED: False, "include": [], "exclude": []},
            "counter": {CONF_ENABLED: True, "include": [], "exclude": []},
            "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
            "output": {CONF_ENABLED: True, "include": [], "exclude": []},
            "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
            "setting": {CONF_ENABLED: True, "include": [], "exclude": []},
            "task": {CONF_ENABLED: False, "include": [], "exclude": []},
            "thermostat": {CONF_ENABLED: True, "include": [], "exclude": []},
        }

        result = _setup_elk_config(conf)

        expected = {
            "panel": {"enabled": True, "included": [True]},
            "zone": {
                "enabled": True,
                "included": [True] * 208,
            },
            "area": {
                "enabled": False,
                "included": [True] * 8,
            },
            "counter": {
                "enabled": True,
                "included": [True] * 64,
            },
            "keypad": {
                "enabled": False,
                "included": [True] * 16,
            },
            "output": {
                "enabled": True,
                "included": [True] * 208,
            },
            "plc": {
                "enabled": False,
                "included": [True] * 256,
            },
            "setting": {
                "enabled": True,
                "included": [True] * 20,
            },
            "task": {
                "enabled": False,
                "included": [True] * 32,
            },
            "thermostat": {
                "enabled": True,
                "included": [True] * 16,
            },
        }
        assert result == expected

    def test_setup_elk_config_with_includes_excludes(self) -> None:
        """Test _setup_elk_config with includes and excludes."""
        conf = {
            CONF_AUTO_CONFIGURE: False,
            "zone": {
                CONF_ENABLED: True,
                "include": [(1, 3)],
                "exclude": [(2, 2)],
            },
            "area": {CONF_ENABLED: False, "include": [], "exclude": []},
            "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
            "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
            "output": {CONF_ENABLED: False, "include": [], "exclude": []},
            "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
            "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
            "task": {CONF_ENABLED: False, "include": [], "exclude": []},
            "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
        }

        result = _setup_elk_config(conf)

        included = result["zone"]["included"]
        assert included[0] is True  # Zone 1 included
        assert included[1] is False  # Zone 2 excluded

    def test_setup_elk_config_invalid_range_raises_error(self) -> None:
        """Test _setup_elk_config with invalid range raises ValueError."""
        conf = {
            CONF_AUTO_CONFIGURE: False,
            "zone": {
                CONF_ENABLED: True,
                "include": [(1, 300)],
                "exclude": [],
            },
            "area": {CONF_ENABLED: False, "include": [], "exclude": []},
            "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
            "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
            "output": {CONF_ENABLED: False, "include": [], "exclude": []},
            "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
            "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
            "task": {CONF_ENABLED: False, "include": [], "exclude": []},
            "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
        }

        with pytest.raises(vol.Invalid):
            _setup_elk_config(conf)


class TestIncludedFunction:
    """Test the _included function."""

    def test_included_basic_range(self) -> None:
        """Test _included with basic range."""
        values = [False] * 10
        _included([(2, 5)], True, values)
        assert values[1] is True  # Zone 2
        assert values[2] is True  # Zone 3
        assert values[3] is True  # Zone 4
        assert values[4] is True  # Zone 5
        assert values[0] is False
        if len(values) > 5:
            assert values[5] is False

    def test_included_multiple_ranges(self) -> None:
        """Test _included with multiple ranges."""
        values = [False] * 10
        _included([(1, 1)], True, values)
        assert values[0] is True  # Zone 1

        values2 = [False] * 10
        _included([(3, 4)], True, values2)
        assert values2[2] is True  # Zone 3
        assert values2[3] is True  # Zone 4

    def test_included_invalid_range_too_high(self) -> None:
        """Test _included with range exceeding list length."""
        values = [False] * 5
        with pytest.raises(vol.Invalid, match="Invalid range"):
            _included([(1, 10)], True, values)

    def test_included_invalid_range_start_greater_than_end(self) -> None:
        """Test _included with start > end."""
        values = [False] * 10
        with pytest.raises(vol.Invalid, match="Invalid range"):
            _included([(5, 3)], True, values)

    def test_included_range_start_zero(self) -> None:
        """Test _included with range starting at 0."""
        values = [False] * 5
        with pytest.raises(vol.Invalid, match="Invalid range"):
            _included([(0, 3)], True, values)


class TestAsyncSetup:
    """Test async_setup function."""

    async def test_async_setup_no_config(self, hass: HomeAssistant) -> None:
        """Test async_setup with no config."""
        with (
            patch(
                "homeassistant.components.elkm1.async_setup_services"
            ) as mock_setup_services,
            patch(
                "homeassistant.components.elkm1.async_discover_devices"
            ) as mock_discover,
            patch("homeassistant.components.elkm1.async_trigger_discovery"),
        ):
            mock_discover.return_value = []

            result = await async_setup(hass, {})

            assert result is True
            mock_setup_services.assert_called_once_with(hass)
            # Discovery should still run
            mock_discover.assert_called_once()

    async def test_async_setup_with_config_new_entry(self, hass: HomeAssistant) -> None:
        """Test async_setup with config for new entry."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "test",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                }
            ]
        }

        with (
            patch(
                "homeassistant.components.elkm1.async_setup_services"
            ) as mock_setup_services,
            patch(
                "homeassistant.components.elkm1.async_discover_devices"
            ) as mock_discover,
            patch(
                "homeassistant.components.elkm1._async_find_matching_config_entry",
                return_value=None,
            ),
        ):
            mock_discover.return_value = []

            result = await async_setup(hass, config)

            assert result is True
            mock_setup_services.assert_called_once_with(hass)

    async def test_async_setup_with_config_existing_entry(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup with config for existing entry."""
        config = {
            DOMAIN: [
                {
                    CONF_HOST: "elk://192.168.1.1",
                    CONF_PREFIX: "test",
                    CONF_USERNAME: "",
                    CONF_PASSWORD: "",
                }
            ]
        }

        mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="test")
        mock_entry.add_to_hass(hass)  # Add entry to hass

        with (
            patch(
                "homeassistant.components.elkm1.async_setup_services"
            ) as mock_setup_services,
            patch(
                "homeassistant.components.elkm1.async_discover_devices"
            ) as mock_discover,
            patch(
                "homeassistant.components.elkm1._async_find_matching_config_entry",
                return_value=mock_entry,
            ),
        ):
            mock_discover.return_value = []

            result = await async_setup(hass, config)

        assert result is True
        mock_setup_services.assert_called_once_with(hass)


class TestAsyncSetupEntry:
    """Test async_setup_entry function."""

    async def test_async_setup_entry_success(self, hass: HomeAssistant) -> None:
        """Test successful async_setup_entry."""
        entry = MockConfigEntry(
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
            patch.object(
                hass.config_entries, "async_forward_entry_setups"
            ) as mock_forward,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data is not None
        mock_forward.assert_called_once()

    async def test_async_setup_entry_config_error(self, hass: HomeAssistant) -> None:
        """Test async_setup_entry with configuration error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
                "zone": {
                    CONF_ENABLED: True,
                    "include": [(1, 300)],
                    "exclude": [],
                },
                "area": {CONF_ENABLED: False, "include": [], "exclude": []},
                "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
                "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
                "output": {CONF_ENABLED: False, "include": [], "exclude": []},
                "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
                "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
                "task": {CONF_ENABLED: False, "include": [], "exclude": []},
                "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
            },
        )

        # The function raises vol.Invalid when configuration validation fails
        # This tests the error handling path for invalid configuration
        with pytest.raises(vol.Invalid, match="Invalid range"):
            await async_setup_entry(hass, entry)

    async def test_async_setup_entry_connection_timeout(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup_entry with connection timeout."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
        )

        mock_elk = MagicMock()

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
            pytest.raises(ConfigEntryNotReady, match="Timeout"),
        ):
            await async_setup_entry(hass, entry)

    async def test_async_setup_entry_auth_failed(self, hass: HomeAssistant) -> None:
        """Test async_setup_entry with authentication failure."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "wrong",
                CONF_AUTO_CONFIGURE: True,
            },
        )

        mock_elk = MagicMock()

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
            pytest.raises(ConfigEntryAuthFailed, match="Auth failed"),
        ):
            await async_setup_entry(hass, entry)

    async def test_async_setup_entry_discovery_success(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup_entry with successful discovery."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "test",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: True,
            },
            unique_id=None,  # Missing unique ID
        )

        mock_elk = MagicMock()
        mock_elk.panel.temperature_units = "C"
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
            result = await async_setup_entry(hass, entry)

        assert result is True
        mock_update.assert_called_once_with(hass, entry, mock_device)

    async def test_async_setup_entry_discovery_failed(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup_entry with discovery failure."""
        entry = MockConfigEntry(
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
                side_effect=OSError("Network error"),
            ),
            patch("homeassistant.components.elkm1.is_ip_address", return_value=True),
            patch.object(hass.config_entries, "async_forward_entry_setups"),
        ):
            # Should continue despite discovery failure
            result = await async_setup_entry(hass, entry)

        assert result is True


class TestAsyncUnloadEntry:
    """Test async_unload_entry function."""

    async def test_async_unload_entry_success(self, hass: HomeAssistant) -> None:
        """Test successful async_unload_entry."""
        mock_elk = MagicMock()
        entry = MockConfigEntry(domain=DOMAIN)
        entry.runtime_data = MagicMock()
        entry.runtime_data.elk = mock_elk

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, entry)

        assert result is True
        mock_elk.disconnect.assert_called_once()

    async def test_async_unload_entry_failed(self, hass: HomeAssistant) -> None:
        """Test failed async_unload_entry."""
        mock_elk = MagicMock()
        entry = MockConfigEntry(domain=DOMAIN)
        entry.runtime_data = MagicMock()
        entry.runtime_data.elk = mock_elk

        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=False
        ):
            result = await async_unload_entry(hass, entry)

        assert result is False
        mock_elk.disconnect.assert_called_once()


class TestAsyncWaitForElkToSync:
    """Test async_wait_for_elk_to_sync function."""

    async def test_async_wait_for_elk_to_sync_success(self) -> None:
        """Test successful sync."""
        mock_elk = MagicMock()

        # Mock the handler registration to call callbacks immediately
        login_callbacks = []
        sync_callbacks = []

        def mock_add_handler(event_type, callback):
            if event_type == "login":
                login_callbacks.append(callback)
                # Simulate successful login
                callback(True)
            elif event_type == "sync_complete":
                sync_callbacks.append(callback)
                # Simulate sync complete
                callback()

        mock_elk.add_handler.side_effect = mock_add_handler

        result = await async_wait_for_elk_to_sync(mock_elk, 10, 30)

        assert result is True
        assert len(login_callbacks) == 1
        assert len(sync_callbacks) == 1

    async def test_async_wait_for_elk_to_sync_login_failed(self) -> None:
        """Test login failure."""
        mock_elk = MagicMock()

        def mock_add_handler(event_type, callback):
            if event_type == "login":
                # Simulate login failure
                callback(False)
            elif event_type == "sync_complete":
                callback()

        mock_elk.add_handler.side_effect = mock_add_handler

        result = await async_wait_for_elk_to_sync(mock_elk, 10, 30)

        assert result is False
        mock_elk.disconnect.assert_called()

    async def test_async_wait_for_elk_to_sync_login_timeout(self) -> None:
        """Test login timeout."""
        mock_elk = MagicMock()

        def mock_add_handler(event_type, callback):
            # Don't call callbacks to simulate timeout
            pass

        mock_elk.add_handler.side_effect = mock_add_handler

        with pytest.raises(TimeoutError):
            await async_wait_for_elk_to_sync(mock_elk, 1, 30)  # Very short timeout

        mock_elk.disconnect.assert_called()

    async def test_async_wait_for_elk_to_sync_sync_timeout(self) -> None:
        """Test sync timeout."""
        mock_elk = MagicMock()

        def mock_add_handler(event_type, callback):
            if event_type == "login":
                # Successful login
                callback(True)
            # Don't call sync_complete callback to simulate timeout

        mock_elk.add_handler.side_effect = mock_add_handler

        with pytest.raises(TimeoutError):
            await async_wait_for_elk_to_sync(mock_elk, 10, 1)  # Very short sync timeout

        mock_elk.disconnect.assert_called()


class TestKeypadHandlers:
    """Test keypad event handling."""

    async def test_keypad_event_fired(self, hass: HomeAssistant) -> None:
        """Test that keypad events are properly fired."""
        mock_elk = MagicMock()
        mock_keypad = MagicMock()
        mock_keypad.name = "Keypad 1"
        mock_keypad.index = 0
        mock_elk.keypads = [mock_keypad]

        # Track the callback that gets registered
        registered_callback = None

        def capture_callback(callback):
            nonlocal registered_callback
            registered_callback = callback

        mock_keypad.add_callback.side_effect = capture_callback

        # Set up the handlers
        _setup_keypad_handlers(hass, mock_elk)

        # Verify callback was registered
        assert registered_callback is not None
        mock_keypad.add_callback.assert_called_once()

        # Test event firing
        events = []

        async def capture_event(event):
            events.append(event)

        hass.bus.async_listen(EVENT_ELKM1_KEYPAD_KEY_PRESSED, capture_event)

        # Simulate keypress
        changeset = {"last_keypress": ("STAR", "*")}
        registered_callback(mock_keypad, changeset)

        await hass.async_block_till_done()

        # Verify event was fired
        assert len(events) == 1
        event_data = events[0].data
        assert event_data["keypad_name"] == "Keypad 1"
        assert event_data["keypad_id"] == 1  # index + 1
        assert event_data["key_name"] == "STAR"
        assert event_data["key"] == "*"

    async def test_keypad_event_no_keypress(self, hass: HomeAssistant) -> None:
        """Test that no event is fired when there's no keypress."""
        mock_elk = MagicMock()
        mock_keypad = MagicMock()
        mock_elk.keypads = [mock_keypad]

        registered_callback = None

        def capture_callback(callback):
            nonlocal registered_callback
            registered_callback = callback

        mock_keypad.add_callback.side_effect = capture_callback

        _setup_keypad_handlers(hass, mock_elk)

        events = []

        async def capture_event(event):
            events.append(event)

        hass.bus.async_listen(EVENT_ELKM1_KEYPAD_KEY_PRESSED, capture_event)

        # Simulate changeset without keypress
        changeset = {"other_change": "value"}
        if registered_callback:
            registered_callback(mock_keypad, changeset)

        await hass.async_block_till_done()

        # Verify no event was fired
        assert len(events) == 0


class TestPrivateFunctions:
    """Test private/helper functions for 100% coverage."""

    def test_async_find_matching_config_entry_found(self, hass: HomeAssistant) -> None:
        """Test _async_find_matching_config_entry when entry is found."""
        # Create a config entry with specific unique_id
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "elk://192.168.1.1"},
            unique_id="test_prefix",
        )
        entry.add_to_hass(hass)

        # Should find the entry
        result = _async_find_matching_config_entry(hass, "test_prefix")
        assert result == entry

    def test_async_find_matching_config_entry_not_found(
        self, hass: HomeAssistant
    ) -> None:
        """Test _async_find_matching_config_entry when entry is not found."""
        # No matching entry
        result = _async_find_matching_config_entry(hass, "nonexistent_prefix")
        assert result is None

    def test_setup_elk_config_value_error_in_included(self) -> None:
        """Test _setup_elk_config when _included raises ValueError."""
        conf = {
            CONF_AUTO_CONFIGURE: False,
            "zone": {
                CONF_ENABLED: True,
                "include": [(1, 10)],
                "exclude": [],
            },
            "area": {CONF_ENABLED: False, "include": [], "exclude": []},
            "counter": {CONF_ENABLED: False, "include": [], "exclude": []},
            "keypad": {CONF_ENABLED: False, "include": [], "exclude": []},
            "output": {CONF_ENABLED: False, "include": [], "exclude": []},
            "plc": {CONF_ENABLED: False, "include": [], "exclude": []},
            "setting": {CONF_ENABLED: False, "include": [], "exclude": []},
            "task": {CONF_ENABLED: False, "include": [], "exclude": []},
            "thermostat": {CONF_ENABLED: False, "include": [], "exclude": []},
        }

        # Mock _included to raise ValueError
        with patch("homeassistant.components.elkm1._included") as mock_included:
            mock_included.side_effect = ValueError("Configuration error")

            with pytest.raises(ValueError):
                _setup_elk_config(conf)

    def test_create_elk_connection(self) -> None:
        """Test _create_elk_connection function."""
        conf = {
            CONF_HOST: "elk://192.168.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        }

        with patch("homeassistant.components.elkm1.Elk") as mock_elk_class:
            mock_elk = MagicMock()
            mock_elk_class.return_value = mock_elk

            result = _create_elk_connection(conf)

            # Verify Elk was created with correct config
            mock_elk_class.assert_called_once_with(
                {
                    "url": "elk://192.168.1.1",
                    "userid": "user",
                    "password": "pass",
                }
            )
            # Verify connect was called
            mock_elk.connect.assert_called_once()
            assert result == mock_elk

    async def test_ensure_elk_connection_auth_failed_auth_error(self) -> None:
        """Test _ensure_elk_connection with authentication failure."""
        mock_elk = MagicMock()

        with patch(
            "homeassistant.components.elkm1.async_wait_for_elk_to_sync"
        ) as mock_sync:
            mock_sync.side_effect = Exception("login failed")

            with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
                await _ensure_elk_connection(mock_elk, "192.168.1.1")

            # The function calls disconnect in the exception handler helper
            assert mock_elk.disconnect.call_count >= 1

    async def test_ensure_elk_connection_auth_failed_invalid_error(self) -> None:
        """Test _ensure_elk_connection with invalid credentials error."""
        mock_elk = MagicMock()

        with patch(
            "homeassistant.components.elkm1.async_wait_for_elk_to_sync"
        ) as mock_sync:
            mock_sync.side_effect = Exception("invalid credentials")

            with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
                await _ensure_elk_connection(mock_elk, "192.168.1.1")

            # The function calls disconnect in the exception handler helper
            assert mock_elk.disconnect.call_count >= 1

    async def test_ensure_elk_connection_not_ready_timeout(self) -> None:
        """Test _ensure_elk_connection with timeout error."""
        mock_elk = MagicMock()

        with patch(
            "homeassistant.components.elkm1.async_wait_for_elk_to_sync"
        ) as mock_sync:
            mock_sync.side_effect = TimeoutError("Connection timeout")

            with pytest.raises(ConfigEntryNotReady, match="Timed out connecting"):
                await _ensure_elk_connection(mock_elk, "192.168.1.1")

            # The function calls disconnect in the _raise_not_ready helper
            assert mock_elk.disconnect.call_count >= 1

    async def test_ensure_elk_connection_sync_failed(self) -> None:
        """Test _ensure_elk_connection when sync returns False."""
        mock_elk = MagicMock()

        with patch(
            "homeassistant.components.elkm1.async_wait_for_elk_to_sync"
        ) as mock_sync:
            mock_sync.return_value = False  # Sync failed

            with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
                await _ensure_elk_connection(mock_elk, "192.168.1.1")

            # The function calls disconnect in the _raise_auth_failed helper
            assert mock_elk.disconnect.call_count >= 1

    async def test_ensure_elk_connection_other_exception(self) -> None:
        """Test _ensure_elk_connection with generic exception."""
        mock_elk = MagicMock()

        with patch(
            "homeassistant.components.elkm1.async_wait_for_elk_to_sync"
        ) as mock_sync:
            mock_sync.side_effect = RuntimeError("Unknown error")

            with pytest.raises(RuntimeError, match="Unknown error"):
                await _ensure_elk_connection(mock_elk, "192.168.1.1")

            # The function calls disconnect in the exception handler
            assert mock_elk.disconnect.call_count >= 1

    async def test_async_setup_entry_setup_elk_config_error(
        self, hass: HomeAssistant
    ) -> None:
        """Test async_setup_entry when _setup_elk_config raises ValueError."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "elk://192.168.1.1",
                CONF_PREFIX: "",
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_AUTO_CONFIGURE: False,
            },
        )

        with patch("homeassistant.components.elkm1._setup_elk_config") as mock_setup:
            mock_setup.side_effect = ValueError("Configuration error")

            result = await async_setup_entry(hass, entry)
            assert result is False
