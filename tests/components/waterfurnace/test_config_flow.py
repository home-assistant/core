"""Test the WaterFurnace config flow."""

from unittest.mock import AsyncMock, Mock

import pytest
from waterfurnace.waterfurnace import WFCredentialError, WFException

from homeassistant.components.waterfurnace.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_waterfurnace_client: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WaterFurnace test_user"
    assert result["data"] == {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    assert result["result"].unique_id == "TEST_GWID_12345"

    # Verify login was called (once during config flow, once during setup)
    assert mock_waterfurnace_client.login.called


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WFCredentialError("Invalid credentials"), "invalid_auth"),
        (WFException("Connection failed"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_exceptions(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test user flow with invalid credentials."""
    mock_waterfurnace_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "bad_user", CONF_PASSWORD: "bad_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Verify we can recover from the error
    mock_waterfurnace_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_no_gwid(
    hass: HomeAssistant, mock_waterfurnace_client: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow with invalid credentials."""
    mock_waterfurnace_client.gwid = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "bad_user",
            CONF_PASSWORD: "bad_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_waterfurnace_client.gwid = "TEST_GWID_12345"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(
    hass: HomeAssistant, mock_waterfurnace_client: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful import flow from YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WaterFurnace test_user"
    assert result["data"] == {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
    }
    assert result["result"].unique_id == "TEST_GWID_12345"


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test import flow when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (WFCredentialError("Invalid credentials"), "invalid_auth"),
        (WFException("Connection failed"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_import_flow_exceptions(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    exception: Exception,
    reason: str,
) -> None:
    """Test import flow with connection error."""
    mock_waterfurnace_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_import_flow_no_gwid(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test import flow with connection error."""
    mock_waterfurnace_client.gwid = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
