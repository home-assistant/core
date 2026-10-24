"""Test the V2C sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.v2c.const import DOMAIN
from homeassistant.components.v2c.sensor import _METER_ERROR_OPTIONS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import init_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    assert _METER_ERROR_OPTIONS == [
        "no_error",
        "communication",
        "reading",
        "meter",
        "waiting_wifi",
        "waiting_communication",
        "wrong_ip",
        "meter_not_found",
        "wrong_meter",
        "no_response",
        "clamp_not_connected",
        "illegal_function",
        "illegal_data_address",
        "illegal_data_value",
        "server_device_failure",
        "acknowledge",
        "server_device_busy",
        "negative_acknowledge",
        "memory_parity_error",
        "gateway_path_unavailable",
        "gateway_target_no_resp",
        "server_rtu_inactive244_timeout",
        "invalid_server",
        "crc_error",
        "fc_mismatch",
        "server_id_mismatch",
        "packet_length_error",
        "parameter_count_error",
        "parameter_limit_error",
        "request_queue_full",
        "illegal_ip_or_port",
        "ip_connection_failed",
        "tcp_head_mismatch",
        "empty_message",
        "undefined_error",
    ]


@pytest.mark.usefixtures("mock_v2c_client")
async def test_deprecated_voltage_sensor_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the deprecated voltage sensor issue is linked to the config entry."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{mock_config_entry.entry_id}_voltage_installation",
        config_entry=mock_config_entry,
    )
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    issue_id = f"deprecated_sensor_{mock_config_entry.entry_id}_voltage_installation"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
