"""Test the Hypontech Cloud config flow."""

from typing import cast
from unittest.mock import AsyncMock, Mock

from hyponcloud import KNOWN_OEMS, AuthenticationError
import pytest

from homeassistant.components.hypontech.config_flow import OEM_OPTIONS
from homeassistant.components.hypontech.const import CONF_OEM, DEFAULT_OEM, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

NEXEN_OEM = 4
TEST_ACCOUNT_ID = "2123456789123456789"
TEST_USER_INPUT = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test-password",
    CONF_OEM: str(DEFAULT_OEM),
}
TEST_ENTRY_DATA = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test-password",
    CONF_OEM: DEFAULT_OEM,
}
TEST_REAUTH_INPUT = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test-password",
}


def assert_oem_not_in_schema(result: ConfigFlowResult) -> None:
    """Assert the form data schema does not contain the OEM field."""
    assert CONF_OEM not in {field.schema for field in result["data_schema"].schema}


def test_oem_options_include_portal_url() -> None:
    """Test OEM options include their portal URLs."""
    assert [
        {
            "value": str(oem.id),
            "label": f"{oem.name} ({oem.monitoring_url})",
        }
        for oem in KNOWN_OEMS
    ] == OEM_OPTIONS


async def test_user_flow(
    hass: HomeAssistant, mock_hyponcloud: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == TEST_ENTRY_DATA
    assert result["result"].unique_id == TEST_ACCOUNT_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_with_oem(
    hass: HomeAssistant, mock_hyponcloud: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test a successful user flow with a non-default OEM."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TEST_USER_INPUT, CONF_OEM: str(NEXEN_OEM)}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {**TEST_ENTRY_DATA, CONF_OEM: NEXEN_OEM}
    assert result["result"].unique_id == f"{NEXEN_OEM}:{TEST_ACCOUNT_ID}"
    assert len(mock_setup_entry.mock_calls) == 1
    hyponcloud_class = cast(Mock, mock_hyponcloud.hyponcloud_class)
    assert hyponcloud_class.call_args.kwargs["oem"] == NEXEN_OEM


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
    side_effect: Exception,
    error_message: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_hyponcloud.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_message}

    mock_hyponcloud.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        TEST_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hyponcloud: AsyncMock
) -> None:
    """Test that duplicate entries are prevented based on account ID."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hyponcloud: AsyncMock
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert_oem_not_in_schema(result)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**TEST_REAUTH_INPUT, CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "password"
    assert CONF_OEM not in mock_config_entry.data


async def test_reauth_flow_uses_stored_oem(
    hass: HomeAssistant, mock_hyponcloud: AsyncMock
) -> None:
    """Test reauthentication uses the stored OEM without exposing it."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**TEST_ENTRY_DATA, CONF_OEM: NEXEN_OEM},
        unique_id=f"{NEXEN_OEM}:{TEST_ACCOUNT_ID}",
    )
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert_oem_not_in_schema(result)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**TEST_REAUTH_INPUT, CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    assert mock_config_entry.data[CONF_OEM] == NEXEN_OEM
    hyponcloud_class = cast(Mock, mock_hyponcloud.hyponcloud_class)
    assert hyponcloud_class.call_args.kwargs["oem"] == NEXEN_OEM


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hyponcloud: AsyncMock,
    side_effect: Exception,
    error_message: str,
) -> None:
    """Test reauthentication flow with errors."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert_oem_not_in_schema(result)

    mock_hyponcloud.connect.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**TEST_REAUTH_INPUT, CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_message}

    mock_hyponcloud.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**TEST_REAUTH_INPUT, CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_hyponcloud: AsyncMock
) -> None:
    """Test reauthentication flow with wrong account."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert_oem_not_in_schema(result)

    mock_hyponcloud.get_admin_info.return_value.id = "different_account_id_456"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**TEST_REAUTH_INPUT, CONF_USERNAME: "different@example.com"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
