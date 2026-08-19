"""Tests for the Concord232 config flow."""

from unittest.mock import MagicMock

import requests

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.concord232.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_HOST, CONF_MODE, CONF_NAME, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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
    assert entries[0].data == USER_INPUT
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


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
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
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
