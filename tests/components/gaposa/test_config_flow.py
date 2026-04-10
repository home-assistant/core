"""Test the Gaposa config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pygaposa import FirebaseAuthException, GaposaAuthException
import pytest

from homeassistant import config_entries
from homeassistant.components.gaposa.const import DOMAIN
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Gaposa Gateway"
    assert result2["data"] == USER_INPUT
    # The config entry's unique id should be the account-scoped Gaposa
    # client id returned after a successful login (see conftest mock).
    assert result2["result"].unique_id == TEST_CLIENT_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_aborts_when_already_configured(
    hass: HomeAssistant,
    mock_gaposa: MagicMock,
) -> None:
    """A second setup flow for the same account aborts."""
    MockConfigEntry(
        domain=DOMAIN, data=USER_INPUT, unique_id=TEST_CLIENT_ID
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exc", "expected_error"),
    [
        (GaposaAuthException("bad creds"), "invalid_auth"),
        (FirebaseAuthException("bad firebase token"), "invalid_auth"),
        (ConnectionError(), "cannot_connect"),
        (Exception("boom"), "unknown"),
    ],
)
async def test_form_validation_errors(
    hass: HomeAssistant,
    mock_gaposa_instance: MagicMock,
    mock_gaposa: MagicMock,
    exc: Exception,
    expected_error: str,
) -> None:
    """Each login failure mode surfaces as the right form error."""
    from aiohttp import ClientConnectionError

    # validate_input catches ClientConnectionError; use it for the
    # "cannot connect" case so the right except arm fires.
    if isinstance(exc, ConnectionError):
        exc = ClientConnectionError("boom")

    mock_gaposa_instance.login.side_effect = exc

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_gaposa: MagicMock,
) -> None:
    """A reauth flow updates the stored credentials when login succeeds."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=TEST_CLIENT_ID,
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_config.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_wrong_account_aborts(
    hass: HomeAssistant,
    mock_gaposa_instance: MagicMock,
    mock_gaposa: MagicMock,
) -> None:
    """Reauthing into a different Gaposa account is rejected."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=TEST_CLIENT_ID,
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )

    # Return a different client id on the reauth login.
    mock_gaposa_instance.clients[0][0].id = "someone-elses-client-id"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "different-account-password"}
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"


async def test_reauth_flow_invalid_auth_shows_form_error(
    hass: HomeAssistant,
    mock_gaposa_instance: MagicMock,
    mock_gaposa: MagicMock,
) -> None:
    """If the replacement password still fails auth, the form shows the error."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=TEST_CLIENT_ID,
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )

    mock_gaposa_instance.login.side_effect = GaposaAuthException("still bad")
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "still-bad"}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {"base": "invalid_auth"}
