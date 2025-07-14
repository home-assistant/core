"""Tests for the yolink integration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.yolink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_credentials")
async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_auth_mgr: MagicMock,
    mock_yolink_home: MagicMock,
) -> None:
    """Test we can only remove a device that no longer exists."""
    with (
        patch(
            "homeassistant.components.yolink.api.ConfigEntryAuth",
            return_value=mock_auth_mgr,
        ),
        patch(
            "homeassistant.components.yolink.YoLinkHome",
            return_value=mock_yolink_home,
        ),
    ):
        mock_config_entry = MockConfigEntry(
            entry_id="test",
            domain=DOMAIN,
            title="yolink",
            data={
                "auth_implementation": DOMAIN,
                "token": {
                    "refresh_token": "mock-refresh-token",
                    "access_token": "mock-access-token",
                    "type": "Bearer",
                    "expires_in": 60,
                    "scope": "create",
                },
            },
            options={},
        )
        mock_config_entry.add_to_hass(hass)
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={(DOMAIN, "stale_device_id")},
        )
        device_entries = dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )

        assert len(device_entries) == 1
        device_entry = device_entries[0]
        assert device_entry.identifiers == {(DOMAIN, "stale_device_id")}

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        device_entries = dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        assert len(device_entries) == 0
