"""Tests for the SVS Subwoofer button platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import SVS_ADDRESS, async_init_integration, entity_id

async def test_save_preset_button(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Pressing save_preset_2 sends a single PRESETLOADSAVE write."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.BUTTON]):
        await async_init_integration(hass)

    eid = entity_id(hass, "button", SVS_ADDRESS, "save_preset_2")
    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1

async def test_reconnect_button(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Pressing reconnect drops the BLE client then refreshes."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.BUTTON]):
        await async_init_integration(hass)

    eid = entity_id(hass, "button", SVS_ADDRESS, "reconnect")
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    assert mock_bleak_client.disconnect.await_count >= 1
