"""Tests for the SVS Subwoofer switch platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import SVS_ADDRESS, async_init_integration, entity_id


async def test_turn_on_off(hass: HomeAssistant, mock_bleak_client: MagicMock) -> None:
    """Turning a switch on then off writes 1 then 0 to the device."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.SWITCH]):
        await async_init_integration(hass)

    eid = entity_id(hass, "switch", SVS_ADDRESS, "peq1_enable")

    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1
    assert hass.states.get(eid).state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: eid},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 2
    assert hass.states.get(eid).state == "off"
