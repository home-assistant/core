"""Test the Kiosker binary sensors."""

from unittest.mock import MagicMock, patch

from kiosker import Blackout, ScreensaverState

from homeassistant.components.kiosker.coordinator import KioskerData
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_binary_sensors_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that binary sensor entities are created."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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

        mock_screensaver = ScreensaverState(visible=True, disabled=False)
        mock_blackout = Blackout(visible=True)

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver
        mock_api.blackout_get.return_value = mock_blackout

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=mock_screensaver,
                blackout=mock_blackout,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    # Check that binary sensor entities were created
    expected_binary_sensors = [
        "binary_sensor.kiosker_a98be1ce_blackout",
        "binary_sensor.kiosker_a98be1ce_screensaver",
        "binary_sensor.kiosker_a98be1ce_charging",
    ]

    for sensor_id in expected_binary_sensors:
        state = hass.states.get(sensor_id)
        assert state is not None, f"Binary sensor {sensor_id} was not created"


async def test_blackout_state_active(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout state binary sensor when active."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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

        mock_blackout = Blackout(visible=True, text="Test blackout")

        mock_api.status.return_value = mock_status
        mock_api.blackout_get.return_value = mock_blackout

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=mock_blackout,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=mock_blackout,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check blackout state binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_blackout")
    assert state is not None
    assert state.state == STATE_ON


async def test_blackout_state_inactive(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test blackout state binary sensor when inactive."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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

        mock_blackout = Blackout(visible=False)

        mock_api.status.return_value = mock_status
        mock_api.blackout_get.return_value = mock_blackout

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=mock_blackout,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=mock_blackout,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check blackout state binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_blackout")
    assert state is not None
    assert state.state == STATE_OFF


async def test_screensaver_visible(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test screensaver visibility binary sensor when visible."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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

        mock_screensaver = ScreensaverState(visible=True, disabled=False)

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=mock_screensaver,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=mock_screensaver,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check screensaver visibility binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_screensaver")
    assert state is not None
    assert state.state == STATE_ON


async def test_screensaver_hidden(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test screensaver visibility binary sensor when hidden."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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

        mock_screensaver = ScreensaverState(visible=False, disabled=False)

        mock_api.status.return_value = mock_status
        mock_api.screensaver_get_state.return_value = mock_screensaver

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=mock_screensaver,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=mock_screensaver,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check screensaver visibility binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_screensaver")
    assert state is not None
    assert state.state == STATE_OFF


async def test_charging_binary_sensor_charging(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test charging binary sensor when battery is charging."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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
        mock_status.battery_state = "Charging"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check charging binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_charging")
    assert state is not None
    assert state.state == STATE_ON


async def test_charging_binary_sensor_fully_charged(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test charging binary sensor when battery is fully charged."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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
        mock_status.battery_state = "Fully Charged"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check charging binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_charging")
    assert state is not None
    assert state.state == STATE_ON


async def test_charging_binary_sensor_not_charging(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test charging binary sensor when battery is not charging."""
    with patch(
        "homeassistant.components.kiosker.coordinator.KioskerAPI"
    ) as mock_api_class:
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
        mock_status.battery_state = "not_charging"

        mock_api.status.return_value = mock_status

        # Add the config entry
        mock_config_entry.add_to_hass(hass)

        # Setup the integration
        with patch(
            "homeassistant.components.kiosker.coordinator.KioskerDataUpdateCoordinator._async_update_data"
        ) as mock_update:
            mock_update.return_value = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )

            assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Manually trigger coordinator update to get proper state
            coordinator = mock_config_entry.runtime_data
            coordinator.data = KioskerData(
                status=mock_status,
                screensaver=None,
                blackout=None,
            )
            coordinator.async_update_listeners()
            await hass.async_block_till_done()

    # Check charging binary sensor
    state = hass.states.get("binary_sensor.kiosker_a98be1ce_charging")
    assert state is not None
    assert state.state == STATE_OFF
