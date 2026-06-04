"""Tests for the mobile app integration."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any
from unittest.mock import Mock, patch

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.mobile_app.const import (
    ATTR_DEVICE_NAME,
    CONF_CLOUDHOOK_URL,
    CONF_USER_ID,
    DATA_DELETED_IDS,
    DATA_LIVE_ACTIVITY_TOKENS,
    DATA_STORE,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    STORAGE_VERSION_MINOR,
)
from homeassistant.components.mobile_app.live_activity import (
    async_cleanup_expired_tokens,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import CALL_SERVICE, REGISTER_CLEARTEXT

from tests.common import (
    MockConfigEntry,
    MockUser,
    async_mock_cloud_connection_status,
    async_mock_service,
)


@pytest.mark.usefixtures("create_registrations")
async def test_unload_unloads(hass: HomeAssistant, webhook_client) -> None:
    """Test we clean up when we unload."""
    # Second config entry is the one without encryption
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    webhook_id = config_entry.data["webhook_id"]
    calls = async_mock_service(hass, "test", "mobile_app")

    # Test it works
    await webhook_client.post(f"/api/webhook/{webhook_id}", json=CALL_SERVICE)
    assert len(calls) == 1

    await hass.config_entries.async_unload(config_entry.entry_id)

    # Test it no longer works
    await webhook_client.post(f"/api/webhook/{webhook_id}", json=CALL_SERVICE)
    assert len(calls) == 1


@pytest.mark.usefixtures("create_registrations")
async def test_remove_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test we clean up when we remove entry."""
    for config_entry in hass.config_entries.async_entries("mobile_app"):
        await hass.config_entries.async_remove(config_entry.entry_id)
        assert config_entry.data["webhook_id"] in hass.data[DOMAIN][DATA_DELETED_IDS]

    assert len(device_registry.devices) == 0
    assert len(entity_registry.entities) == 0


async def _test_create_cloud_hook(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    additional_config: dict[str, Any],
    async_active_subscription_return_value: bool,
    additional_steps: Callable[
        [ConfigEntry, Mock, str, Callable[[Any], None]], Awaitable[None]
    ],
) -> None:
    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: "test-webhook-id",
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            **additional_config,
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    cloudhook_change_callback = None

    def mock_listen_cloudhook_change(
        _: HomeAssistant, _webhook_id: str, callback: Callable[[Any], None]
    ):
        """Mock the cloudhook change listener."""
        nonlocal cloudhook_change_callback
        cloudhook_change_callback = callback
        return lambda: None  # Return unsubscribe function

    cloud_hook = "https://hook-url"

    async def mock_get_or_create_cloudhook(_hass: HomeAssistant, _webhook_id: str):
        """Mock creating a cloudhook and trigger the change callback."""
        assert cloudhook_change_callback is not None
        cloudhook_change_callback({CONF_CLOUDHOOK_URL: cloud_hook})
        return cloud_hook

    with (
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=async_active_subscription_return_value,
        ),
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            side_effect=mock_get_or_create_cloudhook,
        ) as mock_async_get_or_create_cloudhook,
        patch(
            "homeassistant.components.cloud.async_listen_cloudhook_change",
            side_effect=mock_listen_cloudhook_change,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        assert cloudhook_change_callback is not None

        await additional_steps(
            config_entry,
            mock_async_get_or_create_cloudhook,
            cloud_hook,
            cloudhook_change_callback,
        )


async def test_create_cloud_hook_on_setup(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test creating a cloud hook during setup."""

    async def additional_steps(
        config_entry: ConfigEntry,
        mock_create_cloudhook: Mock,
        cloud_hook: str,
        cloudhook_change_callback: Callable[[Any], None],
    ) -> None:
        assert config_entry.data[CONF_CLOUDHOOK_URL] == cloud_hook
        mock_create_cloudhook.assert_called_once_with(
            hass, config_entry.data[CONF_WEBHOOK_ID]
        )

    await _test_create_cloud_hook(hass, hass_admin_user, {}, True, additional_steps)


@pytest.mark.parametrize("exception", [CloudNotAvailable, ValueError])
async def test_remove_cloudhook(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
) -> None:
    """Test removing a cloud hook when config entry is removed."""

    async def additional_steps(
        config_entry: ConfigEntry,
        mock_create_cloudhook: Mock,
        cloud_hook: str,
        cloudhook_change_callback: Callable[[Any], None],
    ) -> None:
        webhook_id = config_entry.data[CONF_WEBHOOK_ID]
        assert config_entry.data[CONF_CLOUDHOOK_URL] == cloud_hook
        with patch(
            "homeassistant.components.cloud.async_delete_cloudhook",
            side_effect=exception,
        ) as delete_cloudhook:
            await hass.config_entries.async_remove(config_entry.entry_id)
            await hass.async_block_till_done()
            delete_cloudhook.assert_called_once_with(hass, webhook_id)
            assert str(exception) not in caplog.text

    await _test_create_cloud_hook(hass, hass_admin_user, {}, True, additional_steps)


async def test_create_cloud_hook_aleady_exists(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test creating a cloud hook is not called, when a cloud hook already exists."""
    cloud_hook = "https://hook-url-already-exists"

    async def additional_steps(
        config_entry: ConfigEntry,
        mock_create_cloudhook: Mock,
        _: str,
        cloudhook_change_callback: Callable[[Any], None],
    ) -> None:
        assert config_entry.data[CONF_CLOUDHOOK_URL] == cloud_hook
        mock_create_cloudhook.assert_not_called()

    await _test_create_cloud_hook(
        hass, hass_admin_user, {CONF_CLOUDHOOK_URL: cloud_hook}, True, additional_steps
    )


async def test_create_cloud_hook_after_connection(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test creating a cloud hook when connected to the cloud."""

    async def additional_steps(
        config_entry: ConfigEntry,
        mock_create_cloudhook: Mock,
        cloud_hook: str,
        cloudhook_change_callback: Callable[[Any], None],
    ) -> None:
        assert CONF_CLOUDHOOK_URL not in config_entry.data
        mock_create_cloudhook.assert_not_called()

        async_mock_cloud_connection_status(hass, True)
        await hass.async_block_till_done()

        # Simulate cloudhook creation by calling the callback
        cloudhook_change_callback({CONF_CLOUDHOOK_URL: cloud_hook})
        await hass.async_block_till_done()

        assert config_entry.data[CONF_CLOUDHOOK_URL] == cloud_hook
        mock_create_cloudhook.assert_called_once_with(
            hass, config_entry.data[CONF_WEBHOOK_ID]
        )

    await _test_create_cloud_hook(hass, hass_admin_user, {}, False, additional_steps)


@pytest.mark.parametrize(
    ("cloud_logged_in", "should_cloudhook_exist"),
    [(True, True), (False, False)],
)
async def test_delete_cloud_hook(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    cloud_logged_in: bool,
    should_cloudhook_exist: bool,
) -> None:
    """Test deleting the cloud hook only when logged out of the cloud."""

    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: "test-webhook-id",
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: "https://hook-url-already-exists",
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.cloud.async_is_logged_in",
            return_value=cloud_logged_in,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        assert (CONF_CLOUDHOOK_URL in config_entry.data) == should_cloudhook_exist


async def test_setup_entry_local_only_user_no_cloudhook(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test that cloudhook is not created for local_only users during setup."""
    hass_admin_user.local_only = True

    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: "test-webhook-id",
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
        ) as mock_create_cloudhook,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        # Cloudhook should not be created for local_only user
        assert CONF_CLOUDHOOK_URL not in config_entry.data
        mock_create_cloudhook.assert_not_called()


async def test_setup_entry_local_only_user_cleans_existing_cloudhook(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test that existing cloudhook is cleaned up for local_only users during setup."""
    hass_admin_user.local_only = True

    webhook_id = "test-webhook-id"
    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: webhook_id,
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: "https://hooks.nabu.casa/stale",
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch(
            "homeassistant.components.cloud.async_delete_cloudhook",
        ) as delete_cloudhook,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Existing cloudhook should be removed for local_only user
    assert CONF_CLOUDHOOK_URL not in config_entry.data
    delete_cloudhook.assert_called_once_with(hass, webhook_id)


async def test_remove_entry_on_user_remove(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test removing related config entry, when a user gets removed from HA."""

    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: "test-webhook-id",
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: "https://hook-url-already-exists",
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    await hass.auth.async_remove_user(hass_admin_user)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0


async def test_cloudhook_cleanup_on_disconnect_and_logout(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test cloudhook is cleaned up when cloud disconnects and user is logged out."""
    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: "test-webhook-id",
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: "https://hook-url",
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.cloud.async_is_logged_in",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_is_connected",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        # Cloudhook should still exist
        assert CONF_CLOUDHOOK_URL in config_entry.data

    # Simulate cloud disconnect and logout
    with patch(
        "homeassistant.components.cloud.async_is_logged_in",
        return_value=False,
    ):
        async_mock_cloud_connection_status(hass, False)
        await hass.async_block_till_done()

        # Cloudhook should be removed from config entry
        assert CONF_CLOUDHOOK_URL not in config_entry.data


async def test_cloudhook_persists_on_disconnect_when_logged_in(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test cloudhook persists when cloud disconnects but user is still logged in."""
    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: "test-webhook-id",
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: "https://hook-url",
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.cloud.async_is_logged_in",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_is_connected",
            return_value=True,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        # Cloudhook should exist
        assert CONF_CLOUDHOOK_URL in config_entry.data

        # Simulate cloud disconnect while still logged in
        async_mock_cloud_connection_status(hass, False)
        await hass.async_block_till_done()

        # Cloudhook should still exist because user is still logged in
        assert CONF_CLOUDHOOK_URL in config_entry.data


async def test_cloudhook_change_listener_deletion(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test cloudhook listener removes cloudhook from entry on deletion."""
    webhook_id = "test-webhook-id"
    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: webhook_id,
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: "https://hook-url",
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    cloudhook_change_callback = None

    def mock_listen_cloudhook_change(
        _: HomeAssistant, _webhook_id: str, callback: Callable[[Any], None]
    ):
        """Mock the cloudhook change listener."""
        nonlocal cloudhook_change_callback
        cloudhook_change_callback = callback
        return lambda: None  # Return unsubscribe function

    with (
        patch(
            "homeassistant.components.cloud.async_is_logged_in",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_is_connected",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_listen_cloudhook_change",
            side_effect=mock_listen_cloudhook_change,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        # Cloudhook should exist
        assert CONF_CLOUDHOOK_URL in config_entry.data
        # Change listener should have been registered
        assert cloudhook_change_callback is not None

        # Simulate cloudhook deletion by calling the callback with None
        cloudhook_change_callback(None)
        await hass.async_block_till_done()

        # Cloudhook should be removed from config entry
        assert CONF_CLOUDHOOK_URL not in config_entry.data


async def test_cloudhook_change_listener_update(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test cloudhook change listener updates cloudhook URL in config entry."""
    webhook_id = "test-webhook-id"
    original_url = "https://hook-url"
    config_entry = MockConfigEntry(
        data={
            **REGISTER_CLEARTEXT,
            CONF_WEBHOOK_ID: webhook_id,
            ATTR_DEVICE_NAME: "Test",
            ATTR_DEVICE_ID: "Test",
            CONF_USER_ID: hass_admin_user.id,
            CONF_CLOUDHOOK_URL: original_url,
        },
        domain=DOMAIN,
        title="Test",
    )
    config_entry.add_to_hass(hass)

    cloudhook_change_callback = None

    def mock_listen_cloudhook_change(hass_instance, wh_id: str, callback):
        """Mock the cloudhook change listener."""
        nonlocal cloudhook_change_callback
        cloudhook_change_callback = callback
        return lambda: None  # Return unsubscribe function

    with (
        patch(
            "homeassistant.components.cloud.async_is_logged_in",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_is_connected",
            return_value=True,
        ),
        patch(
            "homeassistant.components.cloud.async_listen_cloudhook_change",
            side_effect=mock_listen_cloudhook_change,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        # Cloudhook should exist with original URL
        assert config_entry.data[CONF_CLOUDHOOK_URL] == original_url
        # Change listener should have been registered
        assert cloudhook_change_callback is not None

        # Simulate cloudhook URL change
        new_url = "https://new-hook-url"
        cloudhook_change_callback({CONF_CLOUDHOOK_URL: new_url})
        await hass.async_block_till_done()

        # Cloudhook URL should be updated in config entry
        assert config_entry.data[CONF_CLOUDHOOK_URL] == new_url

        # Simulate same URL update (should not trigger update)
        cloudhook_change_callback({CONF_CLOUDHOOK_URL: new_url})
        await hass.async_block_till_done()

        # URL should remain the same
        assert config_entry.data[CONF_CLOUDHOOK_URL] == new_url


@pytest.mark.usefixtures("create_registrations")
async def test_unload_preserves_live_activity_tokens(
    hass: HomeAssistant, webhook_client: TestClient
) -> None:
    """Test that live activity tokens survive an unload so they are available after reload."""
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    webhook_id = config_entry.data["webhook_id"]

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "expires_at": dt_util.utcnow().timestamp() + 3600,
            },
        },
    )
    assert resp.status == HTTPStatus.OK
    assert webhook_id in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert webhook_id in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]


@pytest.mark.usefixtures("create_registrations")
async def test_remove_entry_cleans_live_activity_tokens(
    hass: HomeAssistant, webhook_client: TestClient
) -> None:
    """Test that live activity tokens are removed when the entry is deleted."""
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    webhook_id = config_entry.data["webhook_id"]

    resp = await webhook_client.post(
        f"/api/webhook/{webhook_id}",
        json={
            "type": "live_activity_token",
            "data": {
                "tag": "washer_cycle",
                "push_token": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                "expires_at": dt_util.utcnow().timestamp() + 3600,
            },
        },
    )
    assert resp.status == HTTPStatus.OK
    assert webhook_id in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]

    await hass.config_entries.async_remove(config_entry.entry_id)

    assert webhook_id not in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]


async def test_storage_migration_adds_live_activity_tokens(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_admin_user: MockUser,
) -> None:
    """Test that older storage is migrated to include live_activity_tokens."""
    hass_storage[STORAGE_KEY] = {
        "key": STORAGE_KEY,
        "version": 1,
        "minor_version": 1,
        "data": {DATA_DELETED_IDS: []},
    }

    entry = MockConfigEntry(
        data={**REGISTER_CLEARTEXT, CONF_USER_ID: hass_admin_user.id},
        domain=DOMAIN,
        source="registration",
        title="Test",
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert DATA_LIVE_ACTIVITY_TOKENS in hass.data[DOMAIN]
    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS] == {}


async def test_live_activity_expired_tokens_cleaned_at_startup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_admin_user: MockUser,
) -> None:
    """Test that expired tokens are dropped at startup and the store is saved."""
    now = dt_util.utcnow().timestamp()
    expired_ts = now - 1
    valid_ts = now + 3600

    hass_storage[STORAGE_KEY] = {
        "key": STORAGE_KEY,
        "version": STORAGE_VERSION,
        "minor_version": STORAGE_VERSION_MINOR,
        "data": {
            DATA_DELETED_IDS: [],
            DATA_LIVE_ACTIVITY_TOKENS: {
                "wh-1": {
                    "expired_tag": {"token": "old", "expires_at": expired_ts},
                    "valid_tag": {"token": "new", "expires_at": valid_ts},
                },
            },
        },
    }

    entry = MockConfigEntry(
        data={**REGISTER_CLEARTEXT, CONF_USER_ID: hass_admin_user.id},
        domain=DOMAIN,
        source="registration",
        title="Test",
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    expected = {
        "wh-1": {
            "valid_tag": {"token": "new", "expires_at": valid_ts},
        },
    }

    assert hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS] == expected
    saved = hass_storage[STORAGE_KEY]["data"][DATA_LIVE_ACTIVITY_TOKENS]
    assert saved == expected


async def test_live_activity_cleanup_task_removes_expired_tokens(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test that the cleanup task removes expired tokens and saves the store."""
    entry = MockConfigEntry(
        data={**REGISTER_CLEARTEXT, CONF_USER_ID: hass_admin_user.id},
        domain=DOMAIN,
        source="registration",
        title="Test",
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    expired_ts = dt_util.utcnow().timestamp() - 1
    hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]["wh-test"] = {
        "tag1": {"token": "abc", "expires_at": expired_ts},
    }

    with patch.object(hass.data[DOMAIN][DATA_STORE], "async_save") as mock_save:
        await async_cleanup_expired_tokens(hass)

    assert "wh-test" not in hass.data[DOMAIN][DATA_LIVE_ACTIVITY_TOKENS]
    mock_save.assert_called_once()
