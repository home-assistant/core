"""Reauth-flow tests (token re-entry after a 401)."""

from __future__ import annotations

from collections.abc import Coroutine
from typing import Any

from httpx import Response
import respx

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.noonlight.const import CONF_API_TOKEN, DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant


def _start_reauth(hass: HomeAssistant, entry) -> Coroutine[Any, Any, ConfigFlowResult]:
    return hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=dict(entry.data),
    )


@respx.mock
async def test_reauth_success_updates_token(hass: HomeAssistant, setup_entry) -> None:
    """A valid new token aborts as reauth_successful and is stored."""
    # 404 against the bogus probe id == reachable + authorised.
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(404))
    result = await _start_reauth(hass, setup_entry)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "fresh-token"}
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert setup_entry.data[CONF_API_TOKEN] == "fresh-token"


@respx.mock
async def test_reauth_bad_token_shows_error(hass: HomeAssistant, setup_entry) -> None:
    """A still-invalid token shows invalid_auth and leaves the token unchanged."""
    respx.route(method="GET", url__regex=r".*/status").mock(return_value=Response(401))
    result = await _start_reauth(hass, setup_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "still-bad"}
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"
    # Original token is left untouched.
    assert setup_entry.data[CONF_API_TOKEN] == "test-token"


@respx.mock
async def test_reauth_cannot_connect_shows_error(
    hass: HomeAssistant, setup_entry
) -> None:
    """A connection failure during reauth shows a cannot_connect error."""
    respx.route(method="GET", url__regex=r".*/status").mock(
        side_effect=__import__("httpx").ConnectError("down")
    )
    result = await _start_reauth(hass, setup_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "whatever"}
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "cannot_connect"
