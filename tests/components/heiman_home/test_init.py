"""Test the Heiman Home integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.heiman_home import async_migrate_entry, async_unload_entry
from homeassistant.components.heiman_home.const import (
    DOMAIN,
    SERVICE_READ_DEVICE_PROPERTIES,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry

__all__ = [
    "MockConfigEntry",
]


async def test_load_unload_entry(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test loading and unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Test unload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_missing_token(hass: HomeAssistant) -> None:
    """Test setup fails when token is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_with_auth_failure(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup with authentication failure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
        side_effect=ConfigEntryAuthFailed("Token expired"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_service_registration(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service registration on first entry load."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token_1",
                "refresh_token": "test_refresh_token_1",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "home_1",
            "user_id": "user_1",
        },
        unique_id="user_1",
    )
    entry1.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.LOADED
    # Check service is registered
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)


async def test_service_call_device_found(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call when device is found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_read_device_properties = AsyncMock()
    mock_coordinator.get_device = MagicMock(return_value=MagicMock())

    # Create a device registry entry
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test-device-id")},
        name="Test Device",
    )

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Inject mock coordinator after setup (integration will have created the real one)
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call the service with device registry ID
    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        {"device_id": device_entry.id},
        blocking=True,
    )

    # Service handler should translate registry ID to Heiman device_id
    mock_coordinator.async_read_device_properties.assert_called_once_with(
        "test-device-id"
    )


async def test_service_call_device_not_found(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call when device is not found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.get_device = MagicMock(return_value=None)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch.dict(
            hass.data,
            {DOMAIN: {entry.entry_id: mock_coordinator}},
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Call the service - should not raise but log warning
        await hass.services.async_call(
            DOMAIN,
            SERVICE_READ_DEVICE_PROPERTIES,
            {"device_id": "non-existent-device"},
            blocking=True,
        )


async def test_multiple_entries_service_cleanup(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service cleanup when all entries are unloaded."""
    # Setup first entry
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token_1",
                "refresh_token": "test_refresh_token_1",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "home_1",
            "user_id": "user_1",
        },
        unique_id="user_1",
    )
    entry1.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)

    # Setup second entry
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token_2",
                "refresh_token": "test_refresh_token_2",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "home_2",
            "user_id": "user_2",
        },
        unique_id="user_2",
    )
    entry2.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

    assert entry2.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)

    # Unload first entry - service should still exist because entry2 is loaded
    await hass.config_entries.async_unload(entry1.entry_id)
    await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.NOT_LOADED
    assert entry2.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)

    # Unload second entry - service should be removed
    await hass.config_entries.async_unload(entry2.entry_id)
    await hass.async_block_till_done()

    assert entry2.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)


async def test_unload_with_mqtt_disconnect(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload properly disconnects MQTT client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Create mocks for MQTT and API client
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_disconnect = AsyncMock()

    mock_api_client = MagicMock()
    mock_api_client.async_close = AsyncMock()

    mock_coordinator = MagicMock()
    mock_coordinator.mqtt_client = mock_mqtt_client
    mock_coordinator.api_client = mock_api_client

    # Patch the coordinator creation to use our mock
    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Replace runtime_data with our mock after setup
    entry.runtime_data = mock_coordinator

    # Unload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Verify MQTT was disconnected
    mock_mqtt_client.async_disconnect.assert_called_once()
    # Verify API client was closed
    mock_api_client.async_close.assert_called_once()


async def test_service_call_with_empty_device_list(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call with empty device list."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_read_device_properties = AsyncMock()
    mock_coordinator.get_device = MagicMock(return_value=MagicMock())

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Inject mock coordinator after setup
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call the service with empty list - should raise ServiceValidationError
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_READ_DEVICE_PROPERTIES,
            {"device_id": []},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_id_required"


async def test_service_call_with_invalid_device_id_type(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call with invalid device_id type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_read_device_properties = AsyncMock()
    mock_coordinator.get_device = MagicMock(return_value=MagicMock())

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Inject mock coordinator after setup
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call the service with dict - should raise ServiceValidationError
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_READ_DEVICE_PROPERTIES,
            {"device_id": {"key": "value"}},
            blocking=True,
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_device_id_type"


async def test_service_call_multiple_devices(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call with multiple device IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_read_device_properties = AsyncMock()
    mock_coordinator.get_device = MagicMock(return_value=MagicMock())

    # Create device registry entries
    device_registry = dr.async_get(hass)
    device_entry1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test-device-1")},
        name="Test Device 1",
    )
    device_entry2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test-device-2")},
        name="Test Device 2",
    )

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Inject mock coordinator after setup
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call the service with multiple device IDs
    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        {"device_id": [device_entry1.id, device_entry2.id]},
        blocking=True,
    )

    # Service handler should call read_device_properties for both devices
    assert mock_coordinator.async_read_device_properties.call_count == 2


async def test_service_call_device_not_in_any_coordinator(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call when device is not found in any coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.get_device = MagicMock(return_value=None)

    # Create a device registry entry
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test-device-id")},
        name="Test Device",
    )

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Inject mock coordinator after setup
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call the service - should not raise but log warning
    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        {"device_id": device_entry.id},
        blocking=True,
    )

    # Verify that read_device_properties was not called (device not found)
    mock_coordinator.async_read_device_properties.assert_not_called()


async def test_service_call_skip_none_coordinator(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call skips None coordinators and finds device in another."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home1",
            "user_id": "test_user1",
        },
        unique_id="test_user1",
    )
    entry1.add_to_hass(hass)

    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home2",
            "user_id": "test_user2",
        },
        unique_id="test_user2",
    )
    entry2.add_to_hass(hass)

    mock_coordinator1 = MagicMock()
    mock_coordinator1.get_device = MagicMock(return_value=None)

    mock_coordinator2 = MagicMock()
    mock_coordinator2.get_device = MagicMock(return_value=MagicMock())
    mock_coordinator2.async_read_device_properties = AsyncMock()

    # Create a device registry entry linked to entry2
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, "test-device-id")},
        name="Test Device",
    )

    # Setup entry2 only
    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry2.entry_id)
        await hass.async_block_till_done()

    # Set up domain data with entry1 coordinator as None and entry2 coordinator as mock
    hass.data[DOMAIN][entry1.entry_id] = None
    hass.data[DOMAIN][entry2.entry_id] = mock_coordinator2

    # Call service - should skip None coordinator and find in entry2
    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        {"device_id": device_entry.id},
        blocking=True,
    )

    # Verify that read_device_properties was called on entry2 coordinator
    mock_coordinator2.async_read_device_properties.assert_called_once_with(
        "test-device-id"
    )


async def test_setup_entry_oauth2_implementation_unavailable(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup fails when OAuth2 implementation is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.heiman_home.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # When OAuth2 implementation is unavailable, entry should be in SETUP_RETRY state
    # because ConfigEntryNotReady is raised
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test entry migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True


async def test_setup_oauth2_token_reauth_error(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup when OAuth2 token requires re-authentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.OAuth2Session",
            autospec=True,
        ) as mock_oauth_session,
    ):
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=OAuth2TokenRequestReauthError(
                request_info=MagicMock(), domain="heiman"
            )
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_oauth2_token_request_error(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup when OAuth2 token request fails transiently."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.OAuth2Session",
            autospec=True,
        ) as mock_oauth_session,
    ):
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=OAuth2TokenRequestError(
                request_info=MagicMock(), domain="heiman", message="Server error"
            )
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_oauth2_token_value_error(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup when OAuth2 token validation raises ValueError."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.OAuth2Session",
            autospec=True,
        ) as mock_oauth_session,
    ):
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=ValueError("Invalid token format")
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_with_coordinator_none(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload when coordinator is None (e.g., after failed setup)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Simulate failed setup where coordinator is not set
    with patch(
        "homeassistant.components.heiman_home.OAuth2Session",
        autospec=True,
    ) as mock_oauth_session:
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=Exception("Setup failed")
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    # Entry should be in hass.data even if setup failed
    assert DOMAIN in hass.data

    # Now unload - should handle coordinator being None
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True


async def test_unload_with_mqtt_disconnect_exception(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload handles MQTT disconnect exception gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Create mocks for MQTT client
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_disconnect = AsyncMock(
        side_effect=Exception("MQTT disconnect failed")
    )

    mock_api_client = MagicMock()
    mock_api_client.async_close = AsyncMock()

    mock_coordinator = MagicMock()
    mock_coordinator.mqtt_client = mock_mqtt_client
    mock_coordinator.api_client = mock_api_client

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Replace runtime_data with our mock after setup
    entry.runtime_data = mock_coordinator

    # Unload should handle MQTT disconnect exception gracefully
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True


async def test_unload_with_api_client_close_exception(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload handles API client close exception gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Create mocks
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_disconnect = AsyncMock()

    mock_api_client = MagicMock()
    mock_api_client.async_close = AsyncMock(side_effect=Exception("API close failed"))

    mock_coordinator = MagicMock()
    mock_coordinator.mqtt_client = mock_mqtt_client
    mock_coordinator.api_client = mock_api_client

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Replace runtime_data with our mock after setup
    entry.runtime_data = mock_coordinator

    # Unload should handle API close exception gracefully
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True


async def test_service_call_without_heiman_identifier(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test service call when device doesn't have Heiman identifier."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    mock_coordinator = MagicMock()
    mock_coordinator.async_read_device_properties = AsyncMock()
    mock_coordinator.get_device = MagicMock(return_value=MagicMock())

    # Create a device registry entry with different domain identifier
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_domain", "test-device-id")},
        name="Test Device",
    )

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Inject mock coordinator after setup
    hass.data[DOMAIN][entry.entry_id] = mock_coordinator

    # Call service - should log error and continue
    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        {"device_id": device_entry.id},
        blocking=True,
    )

    # Verify that read_device_properties was not called (no valid identifier)
    mock_coordinator.async_read_device_properties.assert_not_called()


async def test_unload_with_coordinator_none_cleanup(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload when coordinator is None triggers service cleanup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Set runtime_data to None to simulate coordinator was never initialized
    entry.runtime_data = None

    # Simulate domain data state where coordinator was never initialized
    # but domain data exists with entry_id and service is registered
    hass.data[DOMAIN] = {entry.entry_id: None}
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        lambda call: None,  # No-op handler
    )

    # Before unload, check the state
    assert entry.entry_id in hass.data.get(DOMAIN, {})

    # Unload should handle coordinator being None and clean up domain data
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True
    # Verify domain data was cleaned up (should be completely removed since it was the last entry)
    # After proper unload, entry_id should not be in domain_data
    assert hass.data.get(DOMAIN, {}).get(entry.entry_id) is None


async def test_unload_with_coordinator_and_service_cleanup(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload with coordinator None cleans up service when domain_data becomes empty.

    This tests the code path where coordinator is None and domain_data cleanup
    triggers service removal.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Set runtime_data to None
    entry.runtime_data = None

    # Simulate domain data with entry_id and empty dict (triggers cleanup path)
    hass.data[DOMAIN] = {entry.entry_id: {}}
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        lambda call: None,
    )

    # Verify service is registered
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)

    # Unload directly via async_unload_entry (skipping config_entries which has different state)
    unload_ok = await async_unload_entry(hass, entry)
    await hass.async_block_till_done()

    assert unload_ok is True
    # Domain data should be cleaned up
    assert hass.data.get(DOMAIN) is None
    # Service should be removed since domain_data was empty
    assert not hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)


async def test_unload_with_multiple_entries_keeps_service(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload with multiple entries keeps service until last entry.

    This tests the scenario where domain_data still has entries
    after unload, so service should not be removed.
    """
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user1",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token2",
                "refresh_token": "test_refresh_token2",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home2",
            "user_id": "test_user2",
        },
        unique_id="test_user2",
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    # Set runtime_data to None for both
    entry1.runtime_data = None
    entry2.runtime_data = None

    # Simulate domain data with two entries
    hass.data[DOMAIN] = {entry1.entry_id: {}, entry2.entry_id: {}}
    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        lambda call: None,
    )

    # Verify service is registered
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)

    # Unload entry1
    unload_ok = await hass.config_entries.async_unload(entry1.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True
    # Domain data should still exist with entry2
    assert entry2.entry_id in hass.data.get(DOMAIN, {})
    # Service should still exist since entry2 is still loaded
    assert hass.services.has_service(DOMAIN, SERVICE_READ_DEVICE_PROPERTIES)
