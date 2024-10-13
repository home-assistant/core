"""Tests for the LCN config flow."""

from unittest.mock import patch

from pypck.connection import PchkAuthenticationError, PchkLicenseError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.lcn.config_flow import LcnFlowHandler, validate_connection
from homeassistant.components.lcn.const import (
    CONF_ACKNOWLEDGE,
    CONF_DIM_MODE,
    CONF_SK_NUM_TRIES,
    DOMAIN,
)
from homeassistant.const import (
    CONF_BASE,
    CONF_DEVICES,
    CONF_ENTITIES,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

CONFIG_DATA = {
    CONF_IP_ADDRESS: "127.0.0.1",
    CONF_PORT: 1234,
    CONF_USERNAME: "lcn",
    CONF_PASSWORD: "lcn",
    CONF_SK_NUM_TRIES: 0,
    CONF_DIM_MODE: "STEPS200",
    CONF_ACKNOWLEDGE: False,
}

CONNECTION_DATA = {CONF_HOST: "pchk", **CONFIG_DATA}

IMPORT_DATA = {
    **CONNECTION_DATA,
    CONF_DEVICES: [],
    CONF_ENTITIES: [],
}


async def test_step_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test for import step."""

    with (
        patch("homeassistant.components.lcn.PchkConnectionManager.async_connect"),
        patch("homeassistant.components.lcn.async_setup", return_value=True),
        patch("homeassistant.components.lcn.async_setup_entry", return_value=True),
    ):
        data = IMPORT_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "pchk"
        assert result["data"] == IMPORT_DATA
        assert issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )


async def test_step_import_existing_host(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test for update of config_entry if imported host already exists."""

    # Create config entry and add it to hass
    mock_data = IMPORT_DATA.copy()
    mock_data.update({CONF_SK_NUM_TRIES: 3, CONF_DIM_MODE: 50})
    mock_entry = MockConfigEntry(domain=DOMAIN, data=mock_data)
    mock_entry.add_to_hass(hass)
    # Initialize a config flow with different data but same host address
    with patch("homeassistant.components.lcn.PchkConnectionManager.async_connect"):
        imported_data = IMPORT_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=imported_data
        )

        # Check if config entry was updated
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "existing_configuration_updated"
        assert mock_entry.source == config_entries.SOURCE_IMPORT
        assert mock_entry.data == IMPORT_DATA
        assert issue_registry.async_get_issue(
            HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
        )


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (PchkAuthenticationError, "authentication_error"),
        (PchkLicenseError, "license_error"),
        (TimeoutError, "connection_refused"),
    ],
)
async def test_step_import_error(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, error, reason
) -> None:
    """Test for error in import is handled correctly."""
    with patch(
        "homeassistant.components.lcn.PchkConnectionManager.async_connect",
        side_effect=error,
    ):
        data = IMPORT_DATA.copy()
        data.update({CONF_HOST: "pchk"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == reason
        assert issue_registry.async_get_issue(DOMAIN, reason)


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    flow = LcnFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user(hass: HomeAssistant) -> None:
    """Test for user step."""
    with (
        patch("homeassistant.components.lcn.PchkConnectionManager.async_connect"),
        patch("homeassistant.components.lcn.async_setup", return_value=True),
        patch("homeassistant.components.lcn.async_setup_entry", return_value=True),
    ):
        data = CONNECTION_DATA.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=data
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == CONNECTION_DATA[CONF_HOST]
        assert result["data"] == {
            **CONNECTION_DATA,
            CONF_DEVICES: [],
            CONF_ENTITIES: [],
        }


async def test_step_user_existing_host(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test for user defined host already exists."""
    entry.add_to_hass(hass)

    with patch("homeassistant.components.lcn.PchkConnectionManager.async_connect"):
        config_data = entry.data.copy()
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=config_data
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_BASE: "already_configured"}


@pytest.mark.parametrize(
    ("error", "errors"),
    [
        (PchkAuthenticationError, {CONF_BASE: "authentication_error"}),
        (PchkLicenseError, {CONF_BASE: "license_error"}),
        (TimeoutError, {CONF_BASE: "connection_refused"}),
    ],
)
async def test_step_user_error(
    hass: HomeAssistant, error: type[Exception], errors: dict[str, str]
) -> None:
    """Test for error in user step is handled correctly."""
    with patch(
        "homeassistant.components.lcn.PchkConnectionManager.async_connect",
        side_effect=error,
    ):
        data = CONNECTION_DATA.copy()
        data.update({CONF_HOST: "pchk"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=data
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors


async def test_step_reconfigure(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test for reconfigure step."""
    entry.add_to_hass(hass)
    old_entry_data = entry.data.copy()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    with (
        patch("homeassistant.components.lcn.PchkConnectionManager.async_connect"),
        patch("homeassistant.components.lcn.async_setup", return_value=True),
        patch("homeassistant.components.lcn.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_DATA.copy(),
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        entry = hass.config_entries.async_get_entry(entry.entry_id)
        assert entry.title == CONNECTION_DATA[CONF_HOST]
        assert entry.data == {**old_entry_data, **CONFIG_DATA}


@pytest.mark.parametrize(
    ("error", "errors"),
    [
        (PchkAuthenticationError, {CONF_BASE: "authentication_error"}),
        (PchkLicenseError, {CONF_BASE: "license_error"}),
        (TimeoutError, {CONF_BASE: "connection_refused"}),
    ],
)
async def test_step_reconfigure_error(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    error: type[Exception],
    errors: dict[str, str],
) -> None:
    """Test for error in reconfigure step is handled correctly."""
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    with patch(
        "homeassistant.components.lcn.PchkConnectionManager.async_connect",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG_DATA.copy(),
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors


async def test_validate_connection() -> None:
    """Test the connection validation."""
    data = CONNECTION_DATA.copy()

    with (
        patch(
            "homeassistant.components.lcn.PchkConnectionManager.async_connect"
        ) as async_connect,
        patch(
            "homeassistant.components.lcn.PchkConnectionManager.async_close"
        ) as async_close,
    ):
        result = await validate_connection(data=data)

    assert async_connect.is_called
    assert async_close.is_called
    assert result is None
