"""Tests for the Apprise config flow."""

from homeassistant.components import apprise
from homeassistant.components.apprise.const import CONF_FILE_URL
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from tests.common import MockConfigEntry

MOCK_DATA = {
    "name": "Apprise",
    "config": "http://localhost:8000/get/apprise",
    "url": "hassio://hostname/accesstoken",
}

MOCK_DATA_CONFIG = {
    "name": "Apprise",
    "config": "http://localhost:8000/get/apprise",
}

MOCK_DATA_URL = {
    "name": "Apprise",
    "url": "hassio://hostname/accesstoken",
}

MOCK_DATA_INVALID = {
    "name": "Apprise",
    "config": "http://1.2.3.4:8000/get/apprise",
}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""

    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_DATA
    )
    assert result2["title"] == f"{MOCK_DATA[CONF_NAME]}"
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == MOCK_DATA


async def test_user_flow_success_config(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""

    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_DATA_CONFIG
    )
    assert result2["title"] == f"{MOCK_DATA_CONFIG[CONF_NAME]}"
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == MOCK_DATA_CONFIG


async def test_user_flow_no_input(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN, context={"source": SOURCE_USER}
    )

    # Continue the flow with just url input
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {}

    # Continue the flow with just url input
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_DATA_URL
    )
    assert result3["title"] == f"{MOCK_DATA_URL[CONF_NAME]}"
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"] == MOCK_DATA_URL


async def test_import_flow(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import triggers config flow and is accepted."""
    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_DATA,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_DATA

    # Deprecation issue should be created
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_apprise"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfigure flow."""

    # Create a mock config entry and add it to hass
    entry = MockConfigEntry(
        domain="apprise",
        data={
            CONF_NAME: "OldName",
            "config": "http://old-config-url",
            CONF_URL: "mailto://user:old@example.com",
        },
        title="Test Apprise",
    )
    entry.add_to_hass(hass)

    # Start reconfigure flow
    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Provide new data to update the config entry
    new_data = {
        CONF_NAME: "NewName",
        CONF_FILE_URL: "http://new-config-url",
        CONF_URL: "mailto://user:new@example.com",
    }

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_data
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    # Check that data is updated
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_NAME] == "NewName"
    assert updated_entry.data[CONF_FILE_URL] == "http://new-config-url"
    assert updated_entry.data[CONF_URL] == "mailto://user:new@example.com"
