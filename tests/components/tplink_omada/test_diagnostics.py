"""Tests for the TP-Link Omada diagnostics."""

from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test config entry diagnostics payload."""

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    config_payload = diagnostics["config_entry"]
    assert config_payload["data"][CONF_HOST]
    assert config_payload["data"][CONF_USERNAME]
    assert config_payload["data"]["password"] == REDACTED

    controller_payload = diagnostics["controller"]
    assert controller_payload["devices"]
    devices = controller_payload["devices"]
    assert devices["last_update_success"]
    assert devices["count"] > 0
    device_list = devices["devices"]
    assert device_list
    sample = next(iter(device_list.values()))
    # Verify essential fields are present
    assert "mac" in sample
    assert "name" in sample
    assert "type" in sample

    # Summaries should be present
    assert "clients_summary" in controller_payload
    assert "device_ports_summary" in controller_payload

    clients_summary = controller_payload["clients_summary"]
    assert clients_summary == {
        "total": 0,
        "active": 0,
        "wireless": 0,
        "guests": 0,
    }

    device_ports = controller_payload["device_ports_summary"]
    assert len(device_ports) >= 1
    first_device = next(iter(device_ports.values()))
    assert first_device["total_ports"] >= 1
    assert (
        first_device["total_ports"]
        == first_device["ports_up"] + first_device["ports_down"]
    )


async def test_diagnostics_summary_with_clients(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_omada_clients_only_client,
) -> None:
    """Verify diagnostics summaries reflect connected client data."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    controller_payload = diagnostics["controller"]
    clients_summary = controller_payload["clients_summary"]
    # connected-clients fixture contains 3 active wireless clients and no guests
    assert clients_summary == {
        "total": 3,
        "active": 3,
        "wireless": 3,
        "guests": 0,
    }
    # No switches were registered in this fixture; device ports summary should be empty
    assert controller_payload["device_ports_summary"] == {}
