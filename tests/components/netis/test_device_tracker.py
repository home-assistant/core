"""Test the Netis Router device_tracker platform.

Devices from the router host list are auto-discovered and tracked as
ScannerEntity entries: online devices report ``home``, offline ones
report ``not_home``.
"""

from __future__ import annotations

import pytest

from homeassistant.components.netis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

ENTRY_ID = "1"

ONLINE_MAC = "AA:BB:CC:DD:EE:FF"
WIFI5_MAC = "11:22:33:44:55:66"
OFFLINE_MAC = "99:88:77:66:55:44"


def _entity_id(hass: HomeAssistant, mac: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "device_tracker", DOMAIN, f"{ENTRY_ID}-{mac}"
    )
    assert entity_id is not None, f"device_tracker {mac} not registered"
    return entity_id


async def test_wired_device_home(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, ONLINE_MAC)).state == "home"


async def test_wifi5_device_home(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, WIFI5_MAC)).state == "home"


async def test_offline_device_not_home(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, OFFLINE_MAC)).state == "not_home"


async def test_wired_device_attributes(hass: HomeAssistant) -> None:
    state = hass.states.get(_entity_id(hass, ONLINE_MAC))
    assert state.attributes["ip_address"] == "192.168.1.100"
    assert state.attributes["host_name"] == "test-laptop"
    assert state.attributes["connection"] == "wired"
    assert state.attributes["down_speed_bps"] == 4096
