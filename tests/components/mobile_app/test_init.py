"""Tests for the mobile app integration."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.cloud import CloudNotAvailable
from homeassistant.components.mobile_app.const import (
    ATTR_DEVICE_NAME,
    CONF_CLOUDHOOK_URL,
    CONF_USER_ID,
    DATA_DELETED_IDS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    additional_steps: Callable[[ConfigEntry, Mock, str], Awaitable[None]],
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

    with (
        patch(
            "homeassistant.components.cloud.async_active_subscription",
            return_value=async_active_subscription_return_value,
        ),
        patch("homeassistant.components.cloud.async_is_logged_in", return_value=True),
        patch("homeassistant.components.cloud.async_is_connected", return_value=True),
        patch(
            "homeassistant.components.cloud.async_get_or_create_cloudhook",
            autospec=True,
        ) as mock_async_get_or_create_cloudhook,
    ):
        cloud_hook = "https://hook-url"
        mock_async_get_or_create_cloudhook.return_value = cloud_hook

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        await additional_steps(
            config_entry, mock_async_get_or_create_cloudhook, cloud_hook
        )


async def test_create_cloud_hook_on_setup(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test creating a cloud hook during setup."""

    async def additional_steps(
        config_entry: ConfigEntry, mock_create_cloudhook: Mock, cloud_hook: str
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
        config_entry: ConfigEntry, mock_create_cloudhook: Mock, cloud_hook: str
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
        config_entry: ConfigEntry, mock_create_cloudhook: Mock, _: str
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
        config_entry: ConfigEntry, mock_create_cloudhook: Mock, cloud_hook: str
    ) -> None:
        assert CONF_CLOUDHOOK_URL not in config_entry.data
        mock_create_cloudhook.assert_not_called()

        async_mock_cloud_connection_status(hass, True)
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
