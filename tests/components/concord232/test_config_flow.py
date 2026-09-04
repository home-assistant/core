"""Tests for the Concord232 config flow."""

import asyncio
from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.concord232 import async_import_yaml
from homeassistant.components.concord232.const import (
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_CODE,
    CONF_HOST,
    CONF_MODE,
    CONF_NAME,
    CONF_PORT,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import setup_integration

from tests.common import MockConfigEntry

USER_INPUT = {CONF_HOST: "localhost", CONF_PORT: 5007}


async def test_user_flow(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "localhost"
    assert result["data"] == USER_INPUT


async def test_user_flow_cannot_connect_recovers(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test connection errors show an error and the flow can recover."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_concord232_client.list_partitions.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same host and port cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test importing YAML platform configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 5007,
            CONF_NAME: "Test Alarm",
            CONF_CODE: "1234",
            CONF_MODE: "silent",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Alarm"
    assert result["data"] == USER_INPUT
    assert result["options"] == {CONF_CODE: "1234", CONF_MODE: "silent"}


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test the import flow aborts when the server is unreachable."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the import flow aborts for an already configured server."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_yaml_platform_creates_entry_and_issue(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML platform setup imports the config and creates an issue."""
    assert await async_setup_component(
        hass,
        ALARM_DOMAIN,
        {
            ALARM_DOMAIN: {
                "platform": DOMAIN,
                CONF_HOST: "localhost",
                CONF_PORT: 5007,
            }
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {
        **USER_INPUT,
        "imported_platforms": [Platform.ALARM_CONTROL_PANEL],
    }
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    # An alarm-only YAML setup must not sprout zone sensors on import;
    # the YAML schema's default name titles the entry
    assert hass.states.get("alarm_control_panel.concord232") is not None
    assert hass.states.get("binary_sensor.front_door") is None


async def test_yaml_platform_import_cannot_connect_issue(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed YAML import creates the cannot-connect issue."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {
            BINARY_SENSOR_DOMAIN: {
                "platform": DOMAIN,
                CONF_HOST: "localhost",
                CONF_PORT: 5007,
            }
        },
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_localhost_5007"
    )


async def test_options_flow(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow sets code and mode."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CODE: "1234", CONF_MODE: "silent"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_CODE: "1234", CONF_MODE: "silent"}


async def test_options_change_takes_effect_without_manual_reload(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test saving options reloads the entry so the panel picks them up."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MODE: "silent"}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_home",
        {"entity_id": "alarm_control_panel.localhost"},
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with("stay", "silent")


async def test_empty_code_option_means_no_code(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an empty code option allows codeless arming."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_CODE: ""})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_away",
        {"entity_id": "alarm_control_panel.localhost"},
        blocking=True,
    )
    mock_concord232_client.arm.assert_called_once_with("away")


async def test_second_import_merges_alarm_options(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test the alarm platform's import enriches the entry the other created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 5007,
            CONF_NAME: "Test Alarm",
            CONF_CODE: "1234",
            CONF_MODE: "silent",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].options == {CONF_CODE: "1234", CONF_MODE: "silent"}
    assert entries[0].title == "Test Alarm"


async def test_import_alongside_other_server_creates_second_entry(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test importing a second server coexists with an unrelated entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "otherhost", CONF_PORT: 5007},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_import_does_not_overwrite_user_entry_options(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stale YAML never overwrites options on a user-configured entry."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_CODE: "5678", CONF_MODE: "audible"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 5007,
            CONF_CODE: "1234",
            CONF_MODE: "silent",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.options == {CONF_CODE: "5678", CONF_MODE: "audible"}


async def test_user_flow_rejects_invalid_port(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test an out-of-range port is rejected by the schema."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "localhost", CONF_PORT: -1}
        )


async def test_import_carries_zone_options(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test exclude_zones and zone_types survive the YAML import."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 5007,
            CONF_EXCLUDE_ZONES: [2],
            CONF_ZONE_TYPES: {1: "door"},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_EXCLUDE_ZONES: [2],
        CONF_ZONE_TYPES: {"1": "door"},
    }


async def test_import_recovery_clears_cannot_connect_issue(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a successful import removes the earlier failed-import issue."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )
    assert result["reason"] == "cannot_connect"
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_localhost_5007"
    )

    mock_concord232_client.list_partitions.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_localhost_5007"
    )
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_options_flow_preserves_zone_options(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test saving code and mode keeps the imported zone settings."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_EXCLUDE_ZONES: [2], CONF_ZONE_TYPES: {"1": "door"}},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CODE: "1234", CONF_MODE: "silent"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_CODE: "1234",
        CONF_MODE: "silent",
        CONF_EXCLUDE_ZONES: [2],
        CONF_ZONE_TYPES: {"1": "door"},
    }


async def test_stale_yaml_does_not_overwrite_later_changes(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test YAML left in place cannot undo options or title changed later."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        title="My Alarm",
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
        options={CONF_CODE: "5678", CONF_MODE: "audible"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 5007,
            CONF_NAME: "Test Alarm",
            CONF_CODE: "1234",
            CONF_MODE: "silent",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.options == {CONF_CODE: "5678", CONF_MODE: "audible"}
    assert entry.title == "My Alarm"


async def test_failed_import_issue_is_scoped_per_server(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test one server importing does not clear another server's failure."""
    mock_concord232_client.list_partitions.side_effect = (
        requests.exceptions.ConnectionError("boom")
    )
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "deadhost", CONF_PORT: 5007},
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_deadhost_5007"
    )

    mock_concord232_client.list_partitions.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect_deadhost_5007"
    )


async def test_cleared_code_survives_reimport(
    hass: HomeAssistant,
    mock_concord232_client: MagicMock,
) -> None:
    """Test clearing the code in options is not undone by stale YAML."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        title="localhost",
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
        options={CONF_CODE: "5678", CONF_MODE: "audible"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MODE: "audible"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CODE] == ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "localhost",
            CONF_PORT: 5007,
            CONF_CODE: "5678",
            CONF_MODE: "audible",
        },
    )
    assert result["reason"] == "already_configured"
    assert entry.options[CONF_CODE] == ""


async def test_concurrent_platform_imports_create_one_entry(
    hass: HomeAssistant, mock_concord232_client: MagicMock
) -> None:
    """Test simultaneous platform imports merge into a single entry."""
    await asyncio.gather(
        async_import_yaml(
            hass,
            {
                CONF_HOST: "localhost",
                CONF_PORT: 5007,
                CONF_NAME: "Test Alarm",
                CONF_CODE: "1234",
                CONF_MODE: "silent",
            },
            Platform.ALARM_CONTROL_PANEL,
        ),
        async_import_yaml(
            hass,
            {CONF_HOST: "localhost", CONF_PORT: 5007},
            Platform.BINARY_SENSOR,
        ),
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Test Alarm"
    assert entries[0].options == {CONF_CODE: "1234", CONF_MODE: "silent"}
    assert sorted(entries[0].data["imported_platforms"]) == [
        Platform.ALARM_CONTROL_PANEL,
        Platform.BINARY_SENSOR,
    ]
