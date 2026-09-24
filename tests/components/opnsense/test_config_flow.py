"""Tests for the OPNsense config flow."""

from unittest.mock import AsyncMock

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseTimeoutError,
)
import pytest

from homeassistant.components.opnsense import OPNsenseSSLError, OPNsenseUnknownFirmware
from homeassistant.components.opnsense.const import CONF_TRACKER_INTERFACES, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from .const import CONFIG_DATA, CONFIG_DATA_IMPORT

# Constants for test values
TEST_URL = "http://router.lan/api"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user(hass: HomeAssistant, mock_opnsense_client: AsyncMock) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Submit user step, should go to interfaces step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "interfaces"

    # Submit interfaces step (simulate user selecting all interfaces)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKER_INTERFACES: []},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == CONFIG_DATA[CONF_URL]
    assert result.get("data") == CONFIG_DATA
    assert result["result"].unique_id == "mocked_unique_id"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (OPNsenseInvalidAuth, "invalid_auth"),
        (OPNsensePrivilegeMissing, "privilege_missing"),
        (OPNsenseInvalidURL, "invalid_url"),
        (OPNsenseSSLError, "ssl_error"),
        (OPNsenseConnectionError, "cannot_connect"),
        (OPNsenseTimeoutError, "cannot_connect"),
        (OPNsenseUnknownFirmware, "unknown_version"),
        (OPNsenseBelowMinFirmware, "invalid_version"),
    ],
)
async def test_user_exceptions(
    hass: HomeAssistant,
    mock_opnsense_client: AsyncMock,
    exc: type[Exception],
    expected: str,
) -> None:
    """Test all exception branches in async_step_user."""
    mock_opnsense_client.validate.side_effect = exc
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected}

    mock_opnsense_client.validate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_config_entry")
async def test_user_unique_id_already_configured(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test user flow aborts when unique ID is already configured."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG_DATA
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_no_unique_id_aborts(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test that the user flow aborts if the router has no unique id."""
    mock_opnsense_client.get_device_unique_id.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, CONF_URL: TEST_URL},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_unique_id"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_on_unknown_error(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test when we have unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_opnsense_client.validate.side_effect = TypeError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "unknown"}

    mock_opnsense_client.validate.side_effect = None

    # Submit user step, should go to interfaces step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_DATA,
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "interfaces"

    # Submit interfaces step
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKER_INTERFACES: []},
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_interfaces_step_with_tracker_interfaces(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> None:
    """Test interfaces step with tracker_interfaces in user_input (covering the missing branch)."""
    # Patch the client to return interfaces
    mock_opnsense_client.return_value.get_device_unique_id.return_value = (
        "unique_id_789"
    )
    mock_opnsense_client.return_value.get_interfaces.return_value = {
        "LAN": {"name": "LAN"},
        "WAN": {"name": "WAN"},
    }

    # Go through user step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**CONFIG_DATA, CONF_VERIFY_SSL: True},
    )
    # Now submit interfaces step with tracker_interfaces
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TRACKER_INTERFACES: ["LAN", "WAN"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRACKER_INTERFACES] == ["LAN", "WAN"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import(hass: HomeAssistant, mock_opnsense_client: AsyncMock) -> None:
    """Test import step."""
    mock_opnsense_client.return_value.get_device_unique_id.return_value = (
        "unique_id_123"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == CONFIG_DATA_IMPORT[CONF_URL]


@pytest.mark.usefixtures(
    "mock_opnsense_client", "mock_setup_entry", "mock_config_entry"
)
async def test_import_unique_id_already_configured(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test import step when unique ID is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    # The deprecation issue must still be created so the YAML block gets removed
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_yaml"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_no_unique_id_aborts(
    hass: HomeAssistant,
    mock_opnsense_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that the import flow aborts and raises a repair if no unique id."""
    mock_opnsense_client.get_device_unique_id.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_unique_id"
    assert issue_registry.async_get_issue(DOMAIN, "import_failed_no_unique_id")


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exc", "reason"),
    [
        (OPNsenseInvalidURL, "invalid_url"),
        (OPNsenseInvalidAuth, "invalid_auth"),
        (OPNsensePrivilegeMissing, "privilege_missing"),
        (OPNsenseSSLError, "ssl_error"),
        (OPNsenseConnectionError, "cannot_connect"),
        (OPNsenseTimeoutError, "cannot_connect"),
        (OPNsenseUnknownFirmware, "unknown_version"),
        (OPNsenseBelowMinFirmware, "invalid_version"),
        (Exception, "unknown"),
    ],
)
async def test_import_exceptions(
    hass: HomeAssistant,
    mock_opnsense_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
    exc: type[Exception],
    reason: str,
) -> None:
    """Test all exception branches in async_step_import."""
    mock_opnsense_client.validate.side_effect = exc
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=CONFIG_DATA_IMPORT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert issue_registry.async_get_issue(DOMAIN, f"import_failed_{reason}")


@pytest.mark.usefixtures("mock_opnsense_client", "mock_setup_entry")
async def test_import_empty_tracker_interfaces(hass: HomeAssistant) -> None:
    """Test import with empty CONF_TRACKER_INTERFACES (should pop the key)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**CONFIG_DATA_IMPORT, CONF_TRACKER_INTERFACES: []},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_TRACKER_INTERFACES not in result["data"]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_missing_interfaces(
    hass: HomeAssistant,
    mock_opnsense_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test import with missing tracker interfaces (should create issue and abort)."""
    mock_opnsense_client.get_interfaces.return_value = {"LAN": {"name": "LAN"}}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={**CONFIG_DATA_IMPORT, CONF_TRACKER_INTERFACES: ["MISSING"]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "import_failed_missing_interfaces"
    assert issue_registry.async_get_issue(DOMAIN, "import_failed_missing_interfaces")
