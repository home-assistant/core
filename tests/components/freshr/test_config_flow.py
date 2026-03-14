"""Test the Fresh-r config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
from pyfreshr.exceptions import LoginError
import pytest

from homeassistant import config_entries
from homeassistant.components.freshr.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {CONF_USERNAME: "test-user", CONF_PASSWORD: "test-pass"}


@pytest.mark.usefixtures("mock_freshr_client")
async def test_form_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test successful config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fresh-r (test-user)"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "test-user"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (LoginError("bad credentials"), "invalid_auth"),
        (RuntimeError("unexpected"), "unknown"),
        (ClientError("network"), "cannot_connect"),
    ],
)
async def test_form_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_freshr_client: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test config flow handles login errors and recovers correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_freshr_client.login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Ensure the flow can recover after providing correct credentials
    mock_freshr_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_freshr_client")
async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow aborts when the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_freshr_client")
async def test_reauth_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauthentication updates the password and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new-pass"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-pass"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (LoginError("bad credentials"), "invalid_auth"),
        (RuntimeError("unexpected"), "unknown"),
        (ClientError("network"), "cannot_connect"),
    ],
)
async def test_reauth_error(
    hass: HomeAssistant,
    mock_freshr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication handles errors and recovers correctly."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_freshr_client.login.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "wrong-pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_freshr_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new-pass"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-pass"


@pytest.mark.usefixtures("mock_freshr_client")
async def test_form_already_configured_case_insensitive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow aborts when the same account is configured with different casing."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**USER_INPUT, CONF_USERNAME: USER_INPUT[CONF_USERNAME].upper()},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
