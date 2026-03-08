"""Test config flow for Swing2Sleep Smarla integration."""

from unittest.mock import MagicMock, patch

from pysmarlaapi.connection.exceptions import (
    AuthenticationException,
    ConnectionException,
)
import pytest

from homeassistant.components.smarla.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MOCK_ACCESS_TOKEN_JSON,
    MOCK_USER_INPUT,
    MOCK_USER_INPUT_MISMATCH,
    MOCK_USER_INPUT_RECONFIGURE,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_config_flow(hass: HomeAssistant) -> None:
    """Test creating a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_ACCESS_TOKEN_JSON["serialNumber"]
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == MOCK_ACCESS_TOKEN_JSON["serialNumber"]


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_malformed_token(hass: HomeAssistant) -> None:
    """Test we show user form on malformed token input."""
    with patch(
        "homeassistant.components.smarla.config_flow.Connection", side_effect=ValueError
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "malformed_token"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (AuthenticationException, "invalid_auth"),
        (ConnectionException, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_validation_exception(
    hass: HomeAssistant,
    mock_connection: MagicMock,
    exception: type[Exception],
    error_key: str,
) -> None:
    """Test we show user form on validation exception."""
    mock_connection.refresh_token.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=MOCK_USER_INPUT,
    )

    mock_connection.refresh_token.side_effect = None

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_key}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort config flow if Smarla device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=MOCK_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_reauth_successful(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test a successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT_RECONFIGURE,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == MOCK_USER_INPUT_RECONFIGURE


@pytest.mark.usefixtures("mock_setup_entry", "mock_connection")
async def test_reauth_mismatch(
    mock_config_entry: MockConfigEntry,
    hass: HomeAssistant,
) -> None:
    """Test a reauthentication flow with mismatched serial number."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT_MISMATCH,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == MOCK_USER_INPUT
