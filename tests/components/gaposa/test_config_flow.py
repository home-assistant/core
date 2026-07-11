"""Test the Gaposa config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientConnectionError
from pygaposa import FirebaseAuthException, GaposaAuthException
import pytest

from homeassistant.components.gaposa.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_CLIENT_ID

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {
    CONF_API_KEY: "test-apikey",
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test-password",
}


async def test_form_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_gaposa: MagicMock,
) -> None:
    """Happy path: the form creates a config entry with the submitted data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gaposa Gateway"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_CLIENT_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_aborts_when_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gaposa: MagicMock,
) -> None:
    """A second setup flow for the same account aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (GaposaAuthException("bad creds"), "invalid_auth"),
        (FirebaseAuthException("bad firebase token"), "invalid_auth"),
        (ClientConnectionError("boom"), "cannot_connect"),
        (Exception("boom"), "unknown"),
    ],
)
async def test_form_validation_errors_recover(
    hass: HomeAssistant,
    mock_gaposa: MagicMock,
    exc: Exception,
    expected_error: str,
) -> None:
    """Each login failure surfaces as the right error, then the user can retry."""
    mock_gaposa.login.side_effect = exc

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_gaposa.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_no_clients_recovers(
    hass: HomeAssistant,
    mock_gaposa: MagicMock,
) -> None:
    """Login succeeds but the account has no clients; user can then retry."""
    real_clients = mock_gaposa.clients
    mock_gaposa.clients = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_clients"}

    mock_gaposa.clients = real_clients
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
