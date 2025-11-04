"""Test the Kiosker services."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.kiosker import convert_rgb_to_hex
from homeassistant.components.kiosker.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_navigate_url_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test navigate_url service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.navigate_url = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        assert len(devices) == 1
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {
                "url": "https://example.com",
            },
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.navigate_url.assert_called_once_with("https://example.com")


async def test_navigate_refresh_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test navigate_refresh service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.navigate_refresh = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "navigate_refresh",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.navigate_refresh.assert_called_once()


async def test_navigate_home_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test navigate_home service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.navigate_home = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "navigate_home",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.navigate_home.assert_called_once()


async def test_navigate_backward_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test navigate_backward service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.navigate_backward = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "navigate_backward",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.navigate_backward.assert_called_once()


async def test_navigate_forward_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test navigate_forward service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.navigate_forward = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "navigate_forward",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.navigate_forward.assert_called_once()


async def test_print_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test print service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.print = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "print",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.print.assert_called_once()


async def test_clear_cookies_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test clear_cookies service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.clear_cookies = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "clear_cookies",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.clear_cookies.assert_called_once()


async def test_clear_cache_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test clear_cache service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.clear_cache = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "clear_cache",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.clear_cache.assert_called_once()


async def test_screensaver_interact_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test screensaver_interact service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.screensaver_interact = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "screensaver_interact",
            {},
            target={"device_id": device_id},
            blocking=True,
        )

        # Verify API was called
        mock_api.screensaver_interact.assert_called_once()


async def test_blackout_set_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout_set service with all parameters."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.blackout_set = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Mock the coordinator's async_request_refresh method
        coordinator = mock_config_entry.runtime_data
        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            # Call the service with all parameters
            await hass.services.async_call(
                DOMAIN,
                "blackout_set",
                {
                    "visible": True,
                    "text": "Test Message",
                    "background": [255, 0, 0],  # RGB red
                    "foreground": "#00FF00",  # Hex green
                    "icon": "alert",
                    "expire": 120,
                    "dismissible": True,
                    "button_background": [0, 0, 255],  # RGB blue
                    "button_foreground": "#FFFF00",  # Hex yellow
                    "button_text": "Dismiss",
                    "sound": 1,
                },
                target={"device_id": device_id},
                blocking=True,
            )

            # Verify coordinator refresh was called
            mock_refresh.assert_called_once()

        # Verify API was called
        mock_api.blackout_set.assert_called_once()

        # Check the blackout object passed to API
        blackout_call = mock_api.blackout_set.call_args[0][0]
        assert blackout_call.visible is True
        assert blackout_call.text == "Test Message"
        assert blackout_call.background == "#ff0000"  # RGB converted to hex
        assert blackout_call.foreground == "#00FF00"  # Hex preserved
        assert blackout_call.icon == "alert"
        assert blackout_call.expire == 120
        assert blackout_call.dismissible is True
        assert blackout_call.buttonBackground == "#0000ff"  # RGB converted to hex
        assert blackout_call.buttonForeground == "#FFFF00"  # Hex preserved
        assert blackout_call.buttonText == "Dismiss"
        assert blackout_call.sound == 1


async def test_blackout_set_service_defaults(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout_set service with default values."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.blackout_set = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Mock the coordinator's async_request_refresh method
        coordinator = mock_config_entry.runtime_data
        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            # Call the service with minimal parameters (testing defaults)
            await hass.services.async_call(
                DOMAIN,
                "blackout_set",
                {},
                target={"device_id": device_id},
                blocking=True,
            )

            # Verify coordinator refresh was called
            mock_refresh.assert_called_once()

        # Verify API was called
        mock_api.blackout_set.assert_called_once()

        # Check the blackout object with default values
        blackout_call = mock_api.blackout_set.call_args[0][0]
        assert blackout_call.visible is True  # Default
        assert blackout_call.text == ""  # Default
        assert blackout_call.background == "#000000"  # Default
        assert blackout_call.foreground == "#FFFFFF"  # Default
        assert blackout_call.icon == ""  # Default
        assert blackout_call.expire == 60  # Default
        assert blackout_call.dismissible is False  # Default
        assert blackout_call.buttonBackground == "#FFFFFF"  # Default
        assert blackout_call.buttonForeground == "#000000"  # Default
        assert blackout_call.buttonText is None  # Default
        assert blackout_call.sound == 0  # Default


async def test_blackout_clear_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout_clear service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.blackout_clear = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        device_id = devices[0].id

        # Mock the coordinator's async_request_refresh method
        coordinator = mock_config_entry.runtime_data
        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            # Call the service
            await hass.services.async_call(
                DOMAIN,
                "blackout_clear",
                {},
                target={"device_id": device_id},
                blocking=True,
            )

            # Verify coordinator refresh was called
            mock_refresh.assert_called_once()

        # Verify API was called
        mock_api.blackout_clear.assert_called_once()


async def test_service_without_device_target_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that services fail when no device is targeted."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Try to call service without target - should raise ServiceValidationError
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "navigate_refresh",
                {},
                blocking=True,
            )

        # Verify the exception has the correct translation attributes
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "no_target_devices"


async def test_convert_rgb_to_hex_function() -> None:
    """Test the convert_rgb_to_hex utility function."""
    # Test with hex string (should be preserved)
    assert convert_rgb_to_hex("#FF0000") == "#FF0000"
    assert convert_rgb_to_hex("#ff0000") == "#ff0000"
    assert convert_rgb_to_hex("#123456") == "#123456"

    # Test with named color string (should be preserved)
    assert convert_rgb_to_hex("red") == "red"
    assert convert_rgb_to_hex("blue") == "blue"
    assert convert_rgb_to_hex("transparent") == "transparent"

    # Test with valid RGB lists
    assert convert_rgb_to_hex([255, 0, 0]) == "#ff0000"
    assert convert_rgb_to_hex([0, 255, 0]) == "#00ff00"
    assert convert_rgb_to_hex([0, 0, 255]) == "#0000ff"
    assert convert_rgb_to_hex([128, 64, 192]) == "#8040c0"
    assert convert_rgb_to_hex([0, 0, 0]) == "#000000"
    assert convert_rgb_to_hex([255, 255, 255]) == "#ffffff"

    # Test bounds checking - values should be clamped to 0-255 range
    assert convert_rgb_to_hex([300, 0, 0]) == "#ff0000"  # 300 clamped to 255
    assert convert_rgb_to_hex([-10, 0, 0]) == "#000000"  # -10 clamped to 0
    assert convert_rgb_to_hex([128, 300, -50]) == "#80ff00"  # Mixed bounds
    assert convert_rgb_to_hex([1000, -1000, 500]) == "#ff00ff"  # Extreme values

    # Test type conversion within RGB lists
    assert convert_rgb_to_hex([255.0, 128.9, 0.1]) == "#ff8000"  # Float to int
    assert convert_rgb_to_hex(["255", "128", "0"]) == "#ff8000"  # String to int

    # Test invalid RGB value types (should fallback to default)
    assert convert_rgb_to_hex([255, "invalid", 0]) == "#000000"
    assert convert_rgb_to_hex([255, None, 0]) == "#000000"
    assert convert_rgb_to_hex([255, [], 0]) == "#000000"

    # Test invalid list lengths (should return default)
    assert convert_rgb_to_hex([255, 0]) == "#000000"  # Too short
    assert convert_rgb_to_hex([255, 0, 0, 128]) == "#000000"  # Too long
    assert convert_rgb_to_hex([]) == "#000000"  # Empty list

    # Test invalid input types (should return default)
    assert convert_rgb_to_hex(None) == "#000000"
    assert convert_rgb_to_hex(123) == "#000000"
    assert convert_rgb_to_hex(123.45) == "#000000"
    assert convert_rgb_to_hex({}) == "#000000"
    assert convert_rgb_to_hex(set()) == "#000000"

    # Test edge cases
    assert convert_rgb_to_hex("") == ""  # Empty string should be preserved
    assert (
        convert_rgb_to_hex("not_hex_not_starting_with_hash")
        == "not_hex_not_starting_with_hash"
    )


async def test_navigate_url_validation(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test URL validation in navigate_url service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.navigate_url = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        assert len(devices) == 1
        device_id = devices[0].id

        # Test valid HTTP URL
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {"url": "https://www.example.com", "device_id": device_id},
            blocking=True,
        )
        mock_api.navigate_url.assert_called_with("https://www.example.com")
        mock_api.navigate_url.reset_mock()

        # Test valid HTTPS URL with path and query
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {"url": "https://www.example.com/path?param=value", "device_id": device_id},
            blocking=True,
        )
        mock_api.navigate_url.assert_called_with(
            "https://www.example.com/path?param=value"
        )
        mock_api.navigate_url.reset_mock()

        # Test valid custom scheme (like kiosker:)
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {"url": "kiosker://reload", "device_id": device_id},
            blocking=True,
        )
        mock_api.navigate_url.assert_called_with("kiosker://reload")
        mock_api.navigate_url.reset_mock()

        # Test other custom schemes
        await hass.services.async_call(
            DOMAIN,
            "navigate_url",
            {"url": "file:///path/to/file.html", "device_id": device_id},
            blocking=True,
        )
        mock_api.navigate_url.assert_called_with("file:///path/to/file.html")
        mock_api.navigate_url.reset_mock()

        # Test URL without scheme (should be rejected)
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "navigate_url",
                {"url": "www.example.com", "device_id": device_id},
                blocking=True,
            )

        # Verify the exception has the correct translation attributes
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "invalid_url_format"
        # Should not call the API
        mock_api.navigate_url.assert_not_called()
        mock_api.navigate_url.reset_mock()

        # Test HTTP URL without domain (should be rejected)
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "navigate_url",
                {"url": "http://", "device_id": device_id},
                blocking=True,
            )

        # Verify the exception has the correct translation attributes
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "invalid_http_url"
        # Should not call the API
        mock_api.navigate_url.assert_not_called()
        mock_api.navigate_url.reset_mock()

        # Test HTTPS URL without domain (should be rejected)
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "navigate_url",
                {"url": "https://", "device_id": device_id},
                blocking=True,
            )

        # Verify the exception has the correct translation attributes
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "invalid_http_url"
        # Should not call the API
        mock_api.navigate_url.assert_not_called()
        mock_api.navigate_url.reset_mock()

        # Test malformed URL that would cause parsing exception
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "navigate_url",
                {"url": "malformed://[invalid", "device_id": device_id},
                blocking=True,
            )

        # Verify the exception has the correct translation attributes
        assert exc_info.value.translation_domain == DOMAIN
        assert exc_info.value.translation_key == "failed_to_parse_url"
        # Should not call the API
        mock_api.navigate_url.assert_not_called()


async def test_update_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test update service."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"

        mock_api.status.return_value = mock_status

        # Add the config entry and setup integration
        mock_config_entry.add_to_hass(hass)

        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {"status": mock_status}
            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        # Get device ID for targeting
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())
        assert len(devices) == 1
        device_id = devices[0].id

        # Mock the coordinator's async_request_refresh method
        coordinator = mock_config_entry.runtime_data
        with patch.object(coordinator, "async_request_refresh") as mock_refresh:
            # Call the service
            await hass.services.async_call(
                DOMAIN,
                "update",
                {},
                target={"device_id": device_id},
                blocking=True,
            )

            # Verify coordinator refresh was called
            mock_refresh.assert_called_once()
