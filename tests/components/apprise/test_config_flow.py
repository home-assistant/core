"""Tests for the Apprise config flow."""

from homeassistant.components import apprise
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from tests.common import MockConfigEntry

MOCK_OPTIONS = {
    "name": "Apprise",
    "config": "http://localhost:8000/get/apprise",
    "url": "hassio://hostname/accesstoken",
}

MOCK_OPTIONS_CONFIG = {
    "name": "Apprise",
    "config": "http://localhost:8000/get/apprise",
}

MOCK_OPTIONS_URL = {
    "name": "Apprise",
    "url": "hassio://hostname/accesstoken",
}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""

    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_OPTIONS
    )
    assert result2["title"] == f"{MOCK_OPTIONS[CONF_NAME]}"
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["options"] == MOCK_OPTIONS


async def test_user_flow_success_config(hass: HomeAssistant) -> None:
    """Test user-initiated config flow."""

    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_OPTIONS_CONFIG
    )
    assert result2["title"] == f"{MOCK_OPTIONS_CONFIG[CONF_NAME]}"
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["options"] == MOCK_OPTIONS_CONFIG


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
        result["flow_id"], user_input=MOCK_OPTIONS_URL
    )
    assert result3["title"] == f"{MOCK_OPTIONS_URL[CONF_NAME]}"
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["options"] == MOCK_OPTIONS_URL


async def test_import_flow(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import triggers config flow and is accepted."""
    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_OPTIONS,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["options"] == MOCK_OPTIONS

    # Deprecation issue should be created
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_apprise"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options after setup."""
    mock_entry = MockConfigEntry(
        domain=apprise.DOMAIN,
        options=MOCK_OPTIONS,
    )
    mock_entry.add_to_hass(hass)

    new_options = {
        "name": "Updated",
        "url": "mailto://user:pass@example.com, mailto://user:pass@gmail.com",
        "config": "",
    }

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=new_options
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == new_options
