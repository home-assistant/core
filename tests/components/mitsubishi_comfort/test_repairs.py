"""Tests for the Mitsubishi Comfort repairs flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.mitsubishi_comfort.const import CONF_ADDRESSES, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import MOCK_MAC, MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("mock_setup_integration")


@pytest.fixture(autouse=True)
def ignore_missing_translations() -> list[str]:
    """Allow the dynamic, MAC-keyed device IP fields."""
    return [
        "component.mitsubishi_comfort.issues.missing_address.fix_flow.step.addresses.data.",
        "component.mitsubishi_comfort.issues.missing_address.fix_flow.step.addresses.data_description.",
    ]


async def _setup_addressless_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose device has no LAN address, raising the issue."""
    assert await async_setup_component(hass, "repairs", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        unique_id="user-12345",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_fix_flow_sets_missing_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix flow records a manually entered IP and resolves the issue."""
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = data["flow_id"]
    assert data["step_id"] == "addresses"
    # The fields are labeled by raw MAC, so the description must pair each MAC
    # with its device name for the user to tell the fields apart.
    assert dr.format_mac(MOCK_MAC) in data["description_placeholders"]["devices"]

    data = await process_repair_fix_flow(
        client, flow_id, json={dr.format_mac(MOCK_MAC): "not-an-ip"}
    )
    assert data["errors"] == {"base": "invalid_ip"}

    data = await process_repair_fix_flow(
        client, flow_id, json={dr.format_mac(MOCK_MAC): "192.168.1.50"}
    )
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.data[CONF_ADDRESSES][dr.format_mac(MOCK_MAC)] == "192.168.1.50"
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_fix_flow_blank_field_keeps_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test leaving a field blank keeps the device addressless.

    The repairs framework deletes the issue when the flow completes; the
    reload the flow schedules re-creates it while any device still lacks an
    address.
    """
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    data = await process_repair_fix_flow(client, data["flow_id"], json={})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert not entry.data.get(CONF_ADDRESSES)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_fix_flow_suggests_cached_ip(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the form pre-fills an IP the DHCP cache saw after setup."""
    entry = await _setup_addressless_entry(hass)
    issue_id = f"missing_address_{entry.entry_id}"

    client = await hass_client()
    with patch(
        "homeassistant.components.mitsubishi_comfort.repairs.async_discovered_service_info",
        return_value=[
            DhcpServiceInfo(
                ip="10.0.0.5",
                hostname="kumo",
                macaddress=MOCK_MAC.replace(":", "").lower(),
            )
        ],
    ):
        data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    assert data["step_id"] == "addresses"
    assert data["data_schema"][0]["description"] == {"suggested_value": "10.0.0.5"}
