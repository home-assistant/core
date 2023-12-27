"""Tests for the mobile app integration."""
from unittest.mock import patch

import pytest

from homeassistant.components.cloud import (
    SIGNAL_CLOUD_CONNECTION_STATE,
    CloudConnectionState,
)
from homeassistant.components.mobile_app.const import (
    ATTR_DEVICE_NAME,
    CONF_CLOUDHOOK_URL,
    CONF_USER_ID,
    DATA_DELETED_IDS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CALL_SERVICE, REGISTER_CLEARTEXT

from tests.common import MockConfigEntry, MockUser, async_mock_service


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


async def test_create_cloud_hook_on_setup(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test creating a cloud hook during setup."""
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

    with patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_is_connected", return_value=True
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook", autospec=True
    ) as mock_create_cloudhook:
        cloud_hook = "https://hook-url"
        mock_create_cloudhook.return_value = cloud_hook

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        assert config_entry.data[CONF_CLOUDHOOK_URL] == cloud_hook
        mock_create_cloudhook.assert_called_once_with(
            hass, config_entry.data[CONF_WEBHOOK_ID]
        )


async def test_create_cloud_hook_after_connection(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test creating a cloud hook when connected to the cloud."""
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

    with patch(
        "homeassistant.components.cloud.async_active_subscription", return_value=False
    ), patch(
        "homeassistant.components.cloud.async_create_cloudhook", autospec=True
    ) as mock_create_cloudhook:
        cloud_hook = "https://hook-url"
        mock_create_cloudhook.return_value = cloud_hook

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED
        assert CONF_CLOUDHOOK_URL not in config_entry.data
        mock_create_cloudhook.assert_not_called()

        async_dispatcher_send(
            hass, SIGNAL_CLOUD_CONNECTION_STATE, CloudConnectionState.CLOUD_CONNECTED
        )
        await hass.async_block_till_done()
        assert config_entry.data[CONF_CLOUDHOOK_URL] == cloud_hook
        mock_create_cloudhook.assert_called_once_with(
            hass, config_entry.data[CONF_WEBHOOK_ID]
        )
