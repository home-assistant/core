"""Test the System Monitor config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.components.systemmonitor.const import CONF_PROCESS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, issue_registry: ir.IssueRegistry
) -> None:
    """Test import."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "processes": ["systemd", "octave-cli"],
            "legacy_resources": [
                "disk_use_percent_/",
                "memory_free_",
                "network_out_eth0",
                "process_systemd",
                "process_octave-cli",
            ],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        "binary_sensor": {"process": ["systemd", "octave-cli"]},
        "resources": [
            "disk_use_percent_/",
            "memory_free_",
            "network_out_eth0",
            "process_systemd",
            "process_octave-cli",
        ],
    }

    assert len(mock_setup_entry.mock_calls) == 1

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue.issue_domain == DOMAIN
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "System Monitor",
    }


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test abort when already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_USER,
        options={},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, issue_registry: ir.IssueRegistry
) -> None:
    """Test abort when already configured for import."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_USER,
        options={
            "binary_sensor": [{CONF_PROCESS: "systemd"}],
            "resources": [
                "disk_use_percent_/",
                "memory_free_",
                "network_out_eth0",
                "process_systemd",
                "process_octave-cli",
            ],
        },
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "processes": ["systemd", "octave-cli"],
            "legacy_resources": [
                "disk_use_percent_/",
                "memory_free_",
                "network_out_eth0",
                "process_systemd",
                "process_octave-cli",
            ],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue.issue_domain == DOMAIN
    assert issue.translation_placeholders == {
        "domain": DOMAIN,
        "integration_title": "System Monitor",
    }


async def test_add_and_remove_processes(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test adding and removing process sensors."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_USER,
        data={},
        options={},
        entry_id="1",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROCESS: ["systemd"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "binary_sensor": {
            CONF_PROCESS: ["systemd"],
        }
    }

    # Add another
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROCESS: ["systemd", "octave-cli"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "binary_sensor": {
            CONF_PROCESS: ["systemd", "octave-cli"],
        },
    }

    assert (
        entity_registry.async_get("binary_sensor.system_monitor_process_systemd")
        is not None
    )
    assert (
        entity_registry.async_get("binary_sensor.system_monitor_process_octave_cli")
        is not None
    )

    # Remove one
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROCESS: ["systemd"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "binary_sensor": {
            CONF_PROCESS: ["systemd"],
        },
    }

    # Remove last
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_PROCESS: [],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "binary_sensor": {CONF_PROCESS: []},
    }

    assert (
        entity_registry.async_get("binary_sensor.systemmonitor_process_systemd") is None
    )
    assert (
        entity_registry.async_get("binary_sensor.systemmonitor_process_octave_cli")
        is None
    )
