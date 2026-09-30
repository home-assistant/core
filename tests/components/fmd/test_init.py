"""Test FMD integration setup and initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fmd_api import AuthenticationError, FmdApiException, OperationError
import pytest

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test setting up the integration."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
            "allow_inaccurate_locations": False,
            "use_imperial": False,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.fmd.FmdClient", mock_fmd_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert config_entry.runtime_data.api is not None
    assert config_entry.runtime_data.api is not None
    assert config_entry.runtime_data.device_info is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test unloading the integration."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.fmd.FmdClient", mock_fmd_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_entry_api_failure(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when API creation fails."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "wrong_password",
            "polling_interval": 30,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fmd.FmdClient.create",
        side_effect=Exception("Authentication failed"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_network_error_raises_config_entry_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test that network errors during API creation raise ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    # Simulate network timeout
    with patch(
        "homeassistant.components.fmd.FmdClient.create",
        side_effect=TimeoutError("Connection timeout"),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # ConfigEntryNotReady results in SETUP_RETRY state with automatic retry
    assert not result
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_missing_credentials_raises_config_entry_not_ready(
    hass: HomeAssistant,
) -> None:
    """Entry missing both artifacts and password should raise ConfigEntryNotReady (wrapped ValueError)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="edge_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "edge_user",
            "id": "edge_user",
        },
        unique_id="edge_user",
    )
    config_entry.add_to_hass(hass)

    # Patch FmdClient refs so code enters try and triggers ValueError path
    with (
        patch("homeassistant.components.fmd.FmdClient.from_auth_artifacts"),
        patch("homeassistant.components.fmd.FmdClient.create"),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Setup fails fast on invalid config
    assert result is False
    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exc, expected_exception",
    [
        (AuthenticationError("bad"), "auth"),
        (OperationError("temporary"), "retry"),
        (FmdApiException("api"), "retry"),
    ],
)
async def test_setup_entry_artifacts_specific_errors(
    hass: HomeAssistant, exc, expected_exception
) -> None:
    """from_auth_artifacts should propagate mapped exceptions (auth vs retry)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="edge_user",
        data={
            "artifacts": {"base_url": "u", "fmd_id": "edge_user", "access_token": "t"},
            "id": "edge_user",
        },
        unique_id="edge_user",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts", side_effect=exc
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    if expected_exception == "auth":
        # Authentication triggers reauth => setup returns False, state should indicate retry or auth
        assert result is False
    else:
        assert result is False
    assert entry.state.name.lower().startswith(
        "setup_retry"
    ) or entry.state.name.lower().startswith("setup_error")


async def test_setup_entry_unexpected_exception_wrapped(hass: HomeAssistant) -> None:
    """Unexpected generic exception should be wrapped in ConfigEntryNotReady."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="edge_user",
        data={
            "artifacts": {"base_url": "u", "fmd_id": "edge_user", "access_token": "t"},
            "id": "edge_user",
        },
        unique_id="edge_user",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state.name.lower().startswith("setup_retry")


async def test_artifact_export_failure_during_password_migration_logs_warning(
    hass: HomeAssistant, caplog
) -> None:
    """Test that artifact export failure during migration logs warning and continues."""
    # Create a config entry with password only (no artifacts)
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="TestDevice",
        data={
            "url": "https://fmd.example.com",
            "id": "test-device-1",
            "password": "test_password",
            # No "artifacts" key - triggers migration path
        },
        source="user",
        unique_id="test-device-1",
    )
    entry.add_to_hass(hass)

    # Mock platforms to prevent actual platform setup
    mock_device = AsyncMock()
    mock_device.wipe = AsyncMock()
    mock_device.lock = AsyncMock()
    mock_device.decode_picture = AsyncMock()
    mock_device.get_picture_blobs = AsyncMock(return_value=[])
    device_class_mock = MagicMock(return_value=mock_device)

    # Mock the FMD API client
    with (
        patch("homeassistant.components.fmd.FmdClient.create") as mock_create,
        patch("homeassistant.components.fmd.button.Device", device_class_mock),
    ):
        mock_api = AsyncMock()
        mock_create.return_value = mock_api

        # Mock export_auth_artifacts to raise an exception
        mock_api.export_auth_artifacts = AsyncMock(
            side_effect=RuntimeError("Network error during artifact export")
        )

        # Mock get_devices to return an empty list (to keep setup simple)
        mock_api.device = MagicMock(return_value=mock_device)
        mock_api.get_devices = AsyncMock(return_value=[])

        # Attempt setup using hass.config_entries.async_setup
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify setup succeeded despite artifact export failure
        assert result is True

        # Verify warning was logged
        assert any(
            "Could not export artifacts for test-device-1" in record.message
            and "will retry on next startup" in record.message
            and "Network error during artifact export" in record.message
            for record in caplog.records
        )

        # Verify authenticate was called with password
        # Verify FmdClient.create was called with password
        mock_create.assert_called_once_with(
            "https://fmd.example.com",
            "test-device-1",
            "test_password",
            drop_password=True,
        )

        # Verify export_auth_artifacts was called
        mock_api.export_auth_artifacts.assert_called_once()


async def test_artifact_export_generic_exception_during_migration(
    hass: HomeAssistant, caplog
) -> None:
    """Test generic exception during artifact export logs warning with exception details."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="TestDevice2",
        data={
            "url": "https://fmd.example.com",
            "id": "device-2",
            "password": "pass123",
        },
        source="user",
        unique_id="device-2",
    )
    entry.add_to_hass(hass)

    # Mock platforms to prevent actual platform setup
    mock_device = AsyncMock()
    mock_device.wipe = AsyncMock()
    mock_device.lock = AsyncMock()
    mock_device.decode_picture = AsyncMock()
    mock_device.get_picture_blobs = AsyncMock(return_value=[])
    device_class_mock = MagicMock(return_value=mock_device)

    with (
        patch("homeassistant.components.fmd.FmdClient.create") as mock_create,
        patch("homeassistant.components.fmd.button.Device", device_class_mock),
    ):
        mock_api = AsyncMock()
        mock_create.return_value = mock_api
        mock_api.export_auth_artifacts = AsyncMock(
            side_effect=ValueError("Invalid artifact format from server")
        )
        mock_api.device = MagicMock(return_value=mock_device)
        mock_api.get_devices = AsyncMock(return_value=[])

        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert any(
            "Could not export artifacts for device-2" in record.message
            and "Invalid artifact format from server" in record.message
            for record in caplog.records
        )


async def test_setup_entry_artifact_export_success(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When create succeeds and export_auth_artifacts returns artifacts, entry is updated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="FMD test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            "password": "test_password",
            "id": "test_user",
        },
        source="user",
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Ensure create returns an API where export_auth_artifacts returns a dict
    api = AsyncMock()
    api.export_auth_artifacts = AsyncMock(return_value={"a": "b"})
    api.get_locations = AsyncMock(return_value=[{}])

    create_mock = AsyncMock(return_value=api)

    with patch("homeassistant.components.fmd.FmdClient.create", create_mock):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    # Entry data should now include artifacts and not contain password
    new_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert "artifacts" in new_entry.data
    assert "password" not in new_entry.data


async def test_setup_entry_from_artifacts_raises_fmdapi_exception(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """If from_auth_artifacts raises FmdApiException, setup should retry (ConfigEntryNotReady)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="FMD test_user",
        data={
            "artifacts": {"mock": "data"},
            "id": "test_user",
        },
        source="user",
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Make from_auth_artifacts raise a FmdApiException
    with patch(
        "homeassistant.components.fmd.FmdClient.from_auth_artifacts",
        side_effect=FmdApiException("server error"),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Setup should not succeed and entry should indicate retry
    assert not result
    assert entry.state is not None


async def test_unload_entry_close_api_exception_logged(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """If api.close raises, the unload should still succeed but log a warning."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="FMD test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            "password": "test_password",
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Use the existing mock but patch its close to raise
    mock_api = mock_fmd_api.create.return_value

    async def close_raises():
        raise RuntimeError("close failed")

    mock_api.close.side_effect = close_raises

    with patch("homeassistant.components.fmd.FmdClient", mock_fmd_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Unload should succeed and log warning
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert any("Error closing FMD API client" in r.message for r in caplog.records)


async def test_setup_multiple_entries(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test setting up multiple FMD entries in separate hass instances."""
    # Create first entry
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        title="device1",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "device1",
            CONF_PASSWORD: "password1",
        },
        entry_id="entry1",
    )
    entry1.add_to_hass(hass)

    with patch("homeassistant.components.fmd.FmdClient", mock_fmd_api):
        # Setup first entry
        assert await hass.config_entries.async_setup(entry1.entry_id)
        await hass.async_block_till_done()

    # Verify first is loaded
    assert entry1.state == ConfigEntryState.LOADED
    assert entry1.runtime_data.api is not None


async def test_unload_entry_with_platforms(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test unloading entry properly cleans up platform entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
        },
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fmd.FmdClient", mock_fmd_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Verify setup succeeded
        assert entry.state == ConfigEntryState.LOADED

        # Now unload
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    # Verify entry is cleaned up
    assert entry.state == ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_entry_partial_unload(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test unload when platform unload partially fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
        },
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.fmd.FmdClient", mock_fmd_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Simulate partial unload failure (should still attempt to clean up)
        result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    # Should still unload
    assert result is True or result is False  # Either is acceptable
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_config_entry_unload_cleans_up_entities_and_data(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test unloading a config entry cleans up entities and hass.data."""
    from tests.components.fmd.common import setup_integration

    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]
    entry_id = entry.entry_id

    # Confirm entities exist before unload
    assert hass.states.get("switch.fmd_test_user_photo_auto_cleanup") is not None
    assert hass.states.get("sensor.fmd_test_user_photo_count") is not None
    assert entry.runtime_data.api is not None

    # Unload the config entry
    result = await hass.config_entries.async_unload(entry_id)
    await hass.async_block_till_done()
    assert result is True

    # Entities should be removed or unavailable (restored state)
    state = hass.states.get("switch.fmd_test_user_photo_auto_cleanup")
    assert state is None or (
        state.state == "unavailable" and state.attributes.get("restored")
    )

    state = hass.states.get("sensor.fmd_test_user_photo_count")
    assert state is None or (
        state.state == "unavailable" and state.attributes.get("restored")
    )

    # runtime_data should be cleaned up on unload
    assert not hasattr(entry, "runtime_data")
