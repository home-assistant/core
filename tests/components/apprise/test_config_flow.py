"""Tests for the Apprise config flow."""

from homeassistant.components import apprise
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from tests.common import MockConfigEntry

MOCK_DATA = {
    "name": "Apprise",
    "config": "http://localhost:8000/get/apprise",
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
    assert result2["title"] == f"Datadog {MOCK_DATA[CONF_NAME]}"
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == MOCK_DATA


async def test_user_flow_retry_after_connection_fail(hass: HomeAssistant) -> None:
    """Test connection failure."""
    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_DATA
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_DATA
    )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"] == MOCK_DATA


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


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


async def test_import_connection_error(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import triggers connection error issue."""
    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_DATA_INVALID,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"

    issue = issue_registry.async_get_issue(
        apprise.DOMAIN, "deprecated_yaml_import_connection_error"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml_import_connection_error"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_import_flow_abort_already_configured_service(
    hass: HomeAssistant,
) -> None:
    """Abort import if the same host/port is already configured."""
    existing_entry = MockConfigEntry(
        domain=apprise.DOMAIN,
        data=MOCK_DATA,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        apprise.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=MOCK_DATA,
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
