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
    assert result["result"].unique_id == "test_account_id"

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


async def test_user_flow_no_devices(
    hass: HomeAssistant, mock_waterfurnace_client: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow with no devices."""
    mock_waterfurnace_client.devices = []

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
    assert result["errors"] == {"base": "no_devices"}

    mock_waterfurnace_client.devices = [Mock(gwid="TEST_GWID_12345")]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_account_id_none(
    hass: HomeAssistant, mock_waterfurnace_client: Mock, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow when account_id is None."""
    mock_waterfurnace_client.account_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


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
    assert result["result"].unique_id == "test_account_id"


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


async def test_import_flow_account_id_none(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test import flow when account_id is None."""
    mock_waterfurnace_client.account_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_import_flow_no_devices(
    hass: HomeAssistant, mock_waterfurnace_client: Mock
) -> None:
    """Test import flow with no devices."""
    mock_waterfurnace_client.devices = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new_user", CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.title == "WaterFurnace new_user"
    assert mock_config_entry.data[CONF_USERNAME] == "new_user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WFCredentialError("Invalid credentials"), "invalid_auth"),
        (WFException("Connection failed"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_reauth_flow_exceptions(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test reauth flow with errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_waterfurnace_client.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "bad_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_waterfurnace_client.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow aborts when a different account is used."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_waterfurnace_client.account_id = "different_account_id"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "other_user", CONF_PASSWORD: "other_password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reauth_flow_no_account_id(
    hass: HomeAssistant,
    mock_waterfurnace_client: Mock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow when no account ID is returned."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_waterfurnace_client.account_id = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "new_password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
