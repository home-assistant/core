"""Test the Vitesy config flow."""

from unittest.mock import AsyncMock

from aiovitesy.exceptions import CannotAuthenticate, CannotConnect, GenericResponseError
import pytest

from homeassistant.components.vitesy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import EMAIL

from tests.common import MockConfigEntry

USER_INPUT = {CONF_EMAIL: EMAIL, CONF_PASSWORD: "hunter2"}


async def test_full_flow(
    hass: HomeAssistant, mock_vitesy_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the happy path creates an entry keyed on the account email."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == EMAIL
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (CannotAuthenticate, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (GenericResponseError, "cannot_connect"),
    ],
)
async def test_form_errors_then_recovers(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test each login failure surfaces an error and the flow can recover."""
    mock_vitesy_client.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_vitesy_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_already_configured(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same account cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test re-authentication updates the stored password."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-pass"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-pass"


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (CannotAuthenticate, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
    ],
)
async def test_reauth_flow_errors_then_recovers(
    hass: HomeAssistant,
    mock_vitesy_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test a failed re-authentication keeps the form open and can recover."""
    mock_config_entry.add_to_hass(hass)
    mock_vitesy_client.login.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-pass"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    mock_vitesy_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-pass"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
