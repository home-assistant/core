"""Tests for Garmin Connect services."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.garmin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            "oauth1_token": "mock_oauth1_token",
            "oauth2_token": "mock_oauth2_token",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_sensor_data() -> dict:
    """Return mock sensor data."""
    return {
        "totalSteps": 10000,
        "restingHeartRate": 60,
        "gear": [
            {
                "uuid": "gear-uuid-1",
                "displayName": "Running Shoes",
                "gearStatusName": "active",
            }
        ],
        "gearStats": [
            {
                "uuid": "gear-uuid-1",
                "totalDistance": 500000.0,
                "totalActivities": 50,
            }
        ],
    }


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> tuple:
    """Set up the integration with mocks and return mock objects."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)
        mock_client.add_body_composition = AsyncMock(return_value={"success": True})
        mock_client.add_blood_pressure = AsyncMock(return_value={"success": True})
        mock_client.create_activity = AsyncMock(return_value={"activityId": 12345})
        mock_client.upload_activity = AsyncMock(return_value={"activityId": 12346})
        mock_client.set_active_gear = AsyncMock(return_value=True)
        mock_client.add_gear_to_activity = AsyncMock(return_value=True)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_auth, mock_client


async def test_service_add_body_composition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test add_body_composition service."""
    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_config_entry.add_to_hass(hass)

        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)
        mock_client.add_body_composition = AsyncMock(return_value={"success": True})

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "add_body_composition",
            {"weight": 75.5},
            blocking=True,
        )

        # Verify the client method was called
        mock_client.add_body_composition.assert_called_once()


async def test_service_add_blood_pressure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test add_blood_pressure service."""
    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_config_entry.add_to_hass(hass)

        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)
        mock_client.add_blood_pressure = AsyncMock(return_value={"success": True})

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "add_blood_pressure",
            {"systolic": 120, "diastolic": 80, "pulse": 70},
            blocking=True,
        )

        mock_client.add_blood_pressure.assert_called_once()


async def test_service_create_activity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test create_activity service."""
    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_config_entry.add_to_hass(hass)

        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)
        mock_client.create_activity = AsyncMock(return_value={"activityId": 12345})

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Call the service
        await hass.services.async_call(
            DOMAIN,
            "create_activity",
            {
                "activity_name": "Test Run",
                "activity_type": "running",
                "start_time": "2024-01-15T07:00:00",
                "duration_seconds": 1800,
            },
            blocking=True,
        )

        mock_client.create_activity.assert_called_once()


async def test_service_no_integration_configured(
    hass: HomeAssistant,
) -> None:
    """Test service raises error when no integration configured."""
    # Don't set up the integration

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "add_body_composition",
            {"weight": 75.5},
            blocking=True,
        )


async def test_services_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test that services are registered after setup."""
    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_config_entry.add_to_hass(hass)

        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check services are registered
    assert hass.services.has_service(DOMAIN, "add_body_composition")
    assert hass.services.has_service(DOMAIN, "add_blood_pressure")
    assert hass.services.has_service(DOMAIN, "create_activity")
    assert hass.services.has_service(DOMAIN, "upload_activity")
    assert hass.services.has_service(DOMAIN, "set_active_gear")
    assert hass.services.has_service(DOMAIN, "add_gear_to_activity")


async def test_services_unregistered_after_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test that services are unregistered after unload."""
    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_config_entry.add_to_hass(hass)

        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.services.has_service(DOMAIN, "add_body_composition")

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Services should be unregistered
    assert not hass.services.has_service(DOMAIN, "add_body_composition")


async def test_service_failure_raises_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sensor_data: dict,
) -> None:
    """Test service raises HomeAssistantError on failure."""
    with (
        patch("homeassistant.components.garmin_connect.GarminAuth") as mock_auth_class,
        patch(
            "homeassistant.components.garmin_connect.GarminClient"
        ) as mock_client_class,
    ):
        mock_config_entry.add_to_hass(hass)

        mock_auth = mock_auth_class.return_value
        mock_auth.oauth1_token = "token1"
        mock_auth.oauth2_token = "token2"
        mock_auth.is_authenticated = True
        mock_auth.refresh_tokens = AsyncMock()

        mock_client = mock_client_class.return_value
        mock_client.fetch_core_data = AsyncMock(return_value=mock_sensor_data)
        mock_client.add_body_composition = AsyncMock(side_effect=Exception("API Error"))

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "add_body_composition",
                {"weight": 75.5},
                blocking=True,
            )
