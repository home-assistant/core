"""Test the Netis Router binary_sensor platform."""

from __future__ import annotations

import pytest

from homeassistant.components.netis.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

ENTRY_ID = "1"


def _entity_id(hass: HomeAssistant, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", DOMAIN, f"{ENTRY_ID}-{key}"
    )
    assert entity_id is not None, f"binary_sensor {key} not registered"
    return entity_id


async def test_wan_online(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "wan_online")).state == "on"


async def test_lte_connected(hass: HomeAssistant) -> None:
    assert hass.states.get(_entity_id(hass, "lte_connected")).state == "on"


async def test_wan_online_interfaces_attribute(hass: HomeAssistant) -> None:
    """The WAN sensor should expose per-interface status as attributes."""
    state = hass.states.get(_entity_id(hass, "wan_online"))
    assert state.attributes["wan_lte"] == "online"
    assert state.attributes["wan1"] == "offline"
