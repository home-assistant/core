"""Test the Kiosker switch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_screensaver_switch_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up switch."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data that coordinator will return
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.disabled = False

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration with proper coordinator mocking
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that the switch entity was created
    state = hass.states.get("switch.kiosker_a98be1ce_disable_screensaver")
    assert state is not None

    # Check entity registry
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("switch.kiosker_a98be1ce_disable_screensaver")
    assert entity is not None
    assert (
        entity.unique_id == "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC_disable_screensaver"
    )


async def test_screensaver_switch_is_on_true(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch is_on property when screensaver is disabled."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data - screensaver is disabled (switch is on)
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.disabled = True

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that the switch is on (screensaver disabled)
    state = hass.states.get("switch.kiosker_a98be1ce_disable_screensaver")
    assert state is not None
    assert state.state == "on"


async def test_screensaver_switch_is_on_false(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch is_on property when screensaver is enabled."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data - screensaver is enabled (switch is off)
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.disabled = False

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that the switch is off (screensaver enabled)
    state = hass.states.get("switch.kiosker_a98be1ce_disable_screensaver")
    assert state is not None
    assert state.state == "off"


async def test_screensaver_switch_is_on_none(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch is_on property when screensaver data is unavailable."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data with no screensaver data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = None

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration with no screensaver data
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                # No screensaver key
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that the switch is unknown (no screensaver data)
    state = hass.states.get("switch.kiosker_a98be1ce_disable_screensaver")
    assert state is not None
    assert state.state == "unknown"


async def test_screensaver_switch_turn_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning on the switch (disabling screensaver)."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.screensaver_set_disabled_state = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.disabled = False

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with (
            patch(
                "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
            ) as mock_update,
            patch(
                "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator.async_request_refresh"
            ) as mock_refresh,
        ):
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }
            mock_refresh.return_value = None

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Turn on the switch
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.kiosker_a98be1ce_disable_screensaver"},
                blocking=True,
            )

            # Verify API was called to disable screensaver
            mock_api.screensaver_set_disabled_state.assert_called_once_with(True)
            mock_refresh.assert_called()


async def test_screensaver_switch_turn_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test turning off the switch (enabling screensaver)."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api.screensaver_set_disabled_state = MagicMock()
        mock_api_class.return_value = mock_api

        # Setup mock data - initially disabled
        mock_status = MagicMock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.disabled = True

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with (
            patch(
                "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
            ) as mock_update,
            patch(
                "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator.async_request_refresh"
            ) as mock_refresh,
        ):
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }
            mock_refresh.return_value = None

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Turn off the switch
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: "switch.kiosker_a98be1ce_disable_screensaver"},
                blocking=True,
            )

            # Verify API was called to enable screensaver
            mock_api.screensaver_set_disabled_state.assert_called_once_with(False)
            mock_refresh.assert_called()


async def test_screensaver_switch_unique_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test switch unique ID generation."""
    with patch("homeassistant.components.kiosker.KioskerAPI") as mock_api_class:
        # Setup mock API
        mock_api = MagicMock()
        mock_api.host = "10.0.1.5"
        mock_api_class.return_value = mock_api

        # Setup mock data with custom device ID
        mock_status = MagicMock()
        mock_status.device_id = "TEST_DEVICE_ID"
        mock_status.model = "iPad Pro"
        mock_status.os_version = "18.0"
        mock_status.app_name = "Kiosker"
        mock_status.app_version = "25.1.1"
        mock_status.battery_level = 85
        mock_status.battery_state = "charging"
        mock_status.last_interaction = "2025-01-01T12:00:00Z"
        mock_status.last_motion = "2025-01-01T11:55:00Z"
        mock_status.last_update = "2025-01-01T12:05:00Z"

        mock_screensaver = MagicMock()
        mock_screensaver.disabled = False

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = {
                "status": mock_status,
                "screensaver": mock_screensaver,
            }

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that the switch entity has the correct unique ID
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get("switch.kiosker_test_dev_disable_screensaver")
    assert entity is not None
    assert entity.unique_id == "TEST_DEVICE_ID_disable_screensaver"
