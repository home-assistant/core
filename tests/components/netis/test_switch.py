"""Test the Netis Router switch platform (WiFi + LED toggles)."""

from __future__ import annotations

import pytest

from homeassistant.components.netis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

ENTRY_ID = "1"


def _entity_id(hass: HomeAssistant, suffix: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{ENTRY_ID}-{suffix}"
    )
    assert entity_id is not None, f"switch {suffix} not registered"
    return entity_id


async def test_wifi_2g_initial_state(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wifi-2G")).state == "on"


async def test_wifi_5g_initial_state(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wifi-5G")).state == "on"


async def test_led_initial_state(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "led")).state == "on"


async def test_turn_off_wifi_2g(
    hass: HomeAssistant, mock_netis_client
) -> None:
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": _entity_id(hass, "wifi-2G")},
        blocking=True,
    )
    mock_netis_client.set_wifi_config.assert_awaited_once_with(
        "2G", {"Enable": "0"}
    )


async def test_turn_on_wifi_5g(
    hass: HomeAssistant, mock_netis_client
) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": _entity_id(hass, "wifi-5G")},
        blocking=True,
    )
    mock_netis_client.set_wifi_config.assert_awaited_once_with(
        "5G", {"Enable": "1"}
    )


async def test_turn_off_led(hass: HomeAssistant, mock_netis_client) -> None:
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": _entity_id(hass, "led")},
        blocking=True,
    )
    mock_netis_client.set_led.assert_awaited_once_with(False)
