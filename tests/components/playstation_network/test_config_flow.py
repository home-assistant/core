"""Test the Playstation Network config flow."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.playstation_network.config_flow import (
    PSNAWPAuthenticationError,
    PSNAWPError,
    PSNAWPInvalidTokenError,
    PSNAWPNotFoundError,
)
from homeassistant.components.playstation_network.const import CONF_NPSSO, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import NPSSO_TOKEN, NPSSO_TOKEN_INVALID_JSON, PSN_ID

from tests.common import MockConfigEntry

MOCK_DATA_ADVANCED_STEP = {CONF_NPSSO: NPSSO_TOKEN}


async def test_manual_config(hass: HomeAssistant, mock_psnawpapi: MagicMock) -> None:
    """Test creating via manual configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "TEST_NPSSO_TOKEN"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == PSN_ID
    assert result["data"] == {
        CONF_NPSSO: "TEST_NPSSO_TOKEN",
    }


async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_psnawpapi: MagicMock,
) -> None:
    """Test we abort form login when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (PSNAWPNotFoundError(), "invalid_account"),
        (PSNAWPAuthenticationError(), "invalid_auth"),
        (PSNAWPError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_form_failures(
    hass: HomeAssistant,
    mock_psnawpapi: MagicMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test we handle a connection error.

    First we generate an error and after fixing it, we are still able to submit.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_psnawpapi.user.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["step_id"] == "user"
    assert result["errors"] == {"base": text_error}

    mock_psnawpapi.user.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NPSSO: NPSSO_TOKEN,
    }


@pytest.mark.usefixtures("mock_psnawpapi")
async def test_parse_npsso_token_failures(
    hass: HomeAssistant,
    mock_psnawp_npsso: MagicMock,
) -> None:
    """Test parse_npsso_token raises the correct exceptions during config flow."""
    mock_psnawp_npsso.side_effect = PSNAWPInvalidTokenError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NPSSO: NPSSO_TOKEN_INVALID_JSON},
    )
    assert result["errors"] == {"base": "invalid_account"}

    mock_psnawp_npsso.side_effect = lambda token: token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: NPSSO_TOKEN},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NPSSO: NPSSO_TOKEN,
    }


@pytest.mark.usefixtures("mock_psnawpapi")
async def test_flow_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data[CONF_NPSSO] == "NEW_NPSSO_TOKEN"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (PSNAWPNotFoundError(), "invalid_account"),
        (PSNAWPAuthenticationError(), "invalid_auth"),
        (PSNAWPError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_flow_reauth_errors(
    hass: HomeAssistant,
    mock_psnawpapi: MagicMock,
    config_entry: MockConfigEntry,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test reauth flow errors."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_psnawpapi.user.side_effect = raise_error
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_psnawpapi.user.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data[CONF_NPSSO] == "NEW_NPSSO_TOKEN"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_psnawpapi")
async def test_flow_reauth_token_error(
    hass: HomeAssistant,
    mock_psnawp_npsso: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow token error."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_psnawp_npsso.side_effect = PSNAWPInvalidTokenError
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_account"}

    mock_psnawp_npsso.side_effect = lambda token: token
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data[CONF_NPSSO] == "NEW_NPSSO_TOKEN"

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("mock_psnawpapi")
async def test_flow_reauth_account_mismatch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_user: MagicMock,
) -> None:
    """Test reauth flow unique_id mismatch."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_user.account_id = "other_account"
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.usefixtures("mock_psnawpapi")
async def test_flow_reconfigure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NPSSO: "NEW_NPSSO_TOKEN"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert config_entry.data[CONF_NPSSO] == "NEW_NPSSO_TOKEN"

    assert len(hass.config_entries.async_entries()) == 1
