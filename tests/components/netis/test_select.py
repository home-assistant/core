"""Test the Netis Router select platform (WiFi transmit power)."""

from __future__ import annotations

import pytest

from homeassistant.components.netis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

ENTRY_ID = "1"


def _entity_id(hass: HomeAssistant, band: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "select", DOMAIN, f"{ENTRY_ID}-txpower-{band}"
    )
    assert entity_id is not None, f"select txpower-{band} not registered"
    return entity_id


async def test_2g_current_option(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "2G")).state == "100"


async def test_5g_current_option(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "5G")).state == "50"


async def test_set_2g_txpower(hass: HomeAssistant, mock_netis_client) -> None:
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": _entity_id(hass, "2G"), "option": "50"},
        blocking=True,
    )
    mock_netis_client.set_wifi_config.assert_awaited_once_with(
        "2G", {"TxPower": "50"}
    )
