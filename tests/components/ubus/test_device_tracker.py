"""Tests for the OpenWrt (ubus) device tracker."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.ubus.const import CONF_DHCP_SOFTWARE, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MAC_GUEST, MAC_LAPTOP, MAC_PHONE, MOCK_CONFIG, MOCK_HOST

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("dhcp_software", "expected_names"),
    [
        pytest.param("dnsmasq", {"my-phone", "my-laptop"}, id="dnsmasq"),
        pytest.param("odhcpd", {"my-phone", "my-laptop"}, id="odhcpd"),
        pytest.param("none", {MAC_PHONE, MAC_LAPTOP}, id="none"),
    ],
)
async def test_only_authorized_clients_are_tracked(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    entity_registry: er.EntityRegistry,
    dhcp_software: str,
    expected_names: set[str],
) -> None:
    """Test that authorized clients become entities and names resolve per backend."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_DHCP_SOFTWARE: dhcp_software},
        title=MOCK_HOST,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}
    assert MAC_GUEST not in {e.unique_id for e in entries}
    assert {e.original_name for e in entries} == expected_names


async def test_setup_scanner_imports_yaml(
    hass: HomeAssistant, mock_ubus: MagicMock
) -> None:
    """Test the legacy YAML platform imports itself into a config entry."""
    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": [
                {
                    "platform": DOMAIN,
                    CONF_HOST: MOCK_HOST,
                    CONF_USERNAME: "root",
                    CONF_PASSWORD: "password",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data == MOCK_CONFIG


async def test_setup_scanner_creates_issue_on_cannot_connect(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is raised when the YAML import cannot connect."""
    mock_ubus.return_value.connect.side_effect = TypeError

    assert await async_setup_component(
        hass,
        "device_tracker",
        {
            "device_tracker": [
                {
                    "platform": DOMAIN,
                    CONF_HOST: MOCK_HOST,
                    CONF_USERNAME: "root",
                    CONF_PASSWORD: "password",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.translation_placeholders == {"host": MOCK_HOST}
