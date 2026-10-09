"""Tests for the Plexilent config flow."""

from unittest.mock import MagicMock

from pyplexilent import PlexilentAuthError, PlexilentConnectionError
import pytest

from homeassistant.components.plexilent.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {CONF_EMAIL: " Me@X.com ", CONF_PASSWORD: "pw"}


async def test_user(hass: HomeAssistant, client: MagicMock) -> None:
    """Signing in creates an entry holding the refresh token, never the password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "me@x.com"
    assert result["data"] == {CONF_EMAIL: "me@x.com", "refresh_token": "r1"}
    assert result["result"].unique_id == "me@x.com"
    client.login.assert_awaited_with("me@x.com", "pw")


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (PlexilentAuthError, "invalid_auth"),
        (PlexilentConnectionError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_errors_recover(
    hass: HomeAssistant, client: MagicMock, error: type[Exception], key: str
) -> None:
    """A failed sign-in shows the error and the form can be submitted again."""
    client.login.side_effect = error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": key}

    client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """The same account cannot be added twice."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Reauthentication asks for the password and stores the new refresh token."""
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    client.login.side_effect = PlexilentAuthError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    client.login.side_effect = None
    client.login.return_value = "r2"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "pw"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["refresh_token"] == "r2"
