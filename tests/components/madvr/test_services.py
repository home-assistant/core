"""Test service APIs for madVR Envy integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.madvr.const import (
    DOMAIN,
    SERVICE_ACTIVATE_PROFILE,
    SERVICE_PRESS_KEY,
    SERVICE_RUN_ACTION,
)
from homeassistant.components.madvr.services import async_setup_services, async_unload_services


async def test_services_dispatch_commands(hass, mock_config_entry, mock_envy_client):
    """Test registered services call through to client commands."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.madvr.MadvrEnvyClient", return_value=mock_envy_client),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, SERVICE_PRESS_KEY, {"key": "MENU"}, blocking=True)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVATE_PROFILE,
        {"group_id": "1", "profile_index": 2},
        blocking=True,
    )
    await hass.services.async_call(DOMAIN, SERVICE_RUN_ACTION, {"action": "restart"}, blocking=True)

    mock_envy_client.key_press.assert_any_await("MENU")
    mock_envy_client.activate_profile.assert_awaited_with("1", 2)
    mock_envy_client.restart.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_services_setup_is_idempotent(hass):
    """Test setting up multiple entries does not double-register services."""
    await async_setup_services(hass)
    await async_setup_services(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_PRESS_KEY)
    await async_unload_services(hass)
