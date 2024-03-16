"""Test the UniFi Protect setup flow."""

from __future__ import annotations

from pyunifiprotect.data import Camera

from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import MockUFPFixture, init_entry


async def test_deprecated_entity(
    hass: HomeAssistant, ufp: MockUFPFixture, hass_ws_client, doorbell: Camera
):
    """Test Deprecate entity repair does not exist by default (new installs)."""

    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None


async def test_deprecated_entity_no_automations(
    hass: HomeAssistant, ufp: MockUFPFixture, hass_ws_client, doorbell: Camera
):
    """Test Deprecate entity repair exists for existing installs."""

    registry = er.async_get(hass)
    registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        f"{doorbell.mac}_hdr_mode",
        config_entry=ufp.entry,
    )

    await init_entry(hass, ufp, [doorbell])

    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"] == "deprecate_hdr_switch":
            issue = i
    assert issue is None
