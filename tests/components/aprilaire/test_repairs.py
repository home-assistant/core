"""Tests for the Aprilaire repairs."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyaprilaire.const import Attribute
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.components.repairs import FlowType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


def _mock_client(mac_address: str) -> AsyncMock:
    """Return a mocked client reporting a MAC address."""
    client = AsyncMock()
    client.stop_listen = MagicMock()
    client.data = {
        Attribute.MAC_ADDRESS: mac_address,
        Attribute.THERMOSTAT_MODES: 0,
        Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS: 0,
        Attribute.CONNECTED: True,
    }
    return client


async def test_wrong_device_repair(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair continues to the reconfigure flow, which fixes the issue."""
    assert await async_setup_component(hass, "repairs", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12:34:56:78:90:ab",
        data={CONF_HOST: "localhost", CONF_PORT: 7000},
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    issue_id = f"wrong_device_{config_entry.entry_id}"

    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        return_value=_mock_client("12:34:56:78:90:cd"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    http_client = await hass_client()
    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "title": config_entry.title,
        "host": "localhost",
        "found": "12:34:56:78:90:cd",
    }

    data = await process_repair_fix_flow(http_client, data["flow_id"], {})
    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "reconfigure"
    flow_type, flow_id = data["next_flow"]
    assert flow_type == FlowType.CONFIG_FLOW
    # The issue stays until a setup with the original thermostat succeeds
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    flow = hass.config_entries.flow.async_get(flow_id)
    assert flow["step_id"] == "reconfigure"
    assert flow["context"]["entry_id"] == config_entry.entry_id

    client = _mock_client("12:34:56:78:90:ab")
    client.read_mac_address_and_wait.return_value = client.data
    with (
        patch(
            "homeassistant.components.aprilaire.config_flow.AprilaireClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_HOST: "192.168.1.10", CONF_PORT: 7000}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_HOST: "192.168.1.10", CONF_PORT: 7000}
    assert config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_wrong_device_repair_reconfigure_fails(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue stays when the reconfigure flow finds a different device."""
    assert await async_setup_component(hass, "repairs", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12:34:56:78:90:ab",
        data={CONF_HOST: "localhost", CONF_PORT: 7000},
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    issue_id = f"wrong_device_{config_entry.entry_id}"

    client = _mock_client("12:34:56:78:90:cd")
    client.read_mac_address_and_wait.return_value = client.data
    with (
        patch(
            "homeassistant.components.aprilaire.config_flow.AprilaireClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
            return_value=client,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        http_client = await hass_client()
        data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
        data = await process_repair_fix_flow(http_client, data["flow_id"], {})
        _, flow_id = data["next_flow"]

        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_HOST: "192.168.1.10", CONF_PORT: 7000}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
