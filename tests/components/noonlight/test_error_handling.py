"""Error-path tests: API failures map to dispatch state + Repair issues.

Covers the coordinator's ``_handle_api_error`` mapping (auth/connection/
response → distinct Repair issues, auth additionally triggering reauth) and
the ERROR transition when a dispatch POST fails.
"""

from __future__ import annotations

from httpx import Response
import respx

from homeassistant.components.noonlight.const import (
    DOMAIN,
    ISSUE_AUTH_FAILED,
    ISSUE_NETWORK_FAILED,
    ISSUE_UNEXPECTED_RESPONSE,
    STATE_ERROR,
)
from homeassistant.components.noonlight.coordinator import NoonlightCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import SANDBOX

_ALARMS = f"{SANDBOX}/dispatch/v1/alarms"


def _coordinator(hass: HomeAssistant, entry) -> NoonlightCoordinator:
    return entry.runtime_data


def _has_issue(hass: HomeAssistant, key, entry_id) -> bool:
    registry = ir.async_get(hass)
    return registry.async_get_issue(DOMAIN, f"{key}_{entry_id}") is not None


@respx.mock
async def test_dispatch_auth_failure_errors_and_creates_issue(
    hass: HomeAssistant, setup_entry
) -> None:
    """An auth failure on dispatch errors, raises an auth issue, and reauths."""
    respx.post(_ALARMS).mock(return_value=Response(401))
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_ERROR
    assert _has_issue(hass, ISSUE_AUTH_FAILED, setup_entry.entry_id)
    # An auth failure should also kick off a reauth flow.
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"].get("source") == "reauth" for f in flows)


@respx.mock
async def test_dispatch_connection_failure_creates_network_issue(
    hass: HomeAssistant, setup_entry
) -> None:
    """A connection failure on dispatch errors and raises a network issue."""
    respx.post(_ALARMS).mock(side_effect=__import__("httpx").ConnectError("x"))
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_ERROR
    assert _has_issue(hass, ISSUE_NETWORK_FAILED, setup_entry.entry_id)


@respx.mock
async def test_dispatch_bad_response_creates_unexpected_issue(
    hass: HomeAssistant, setup_entry
) -> None:
    """A 5xx response on dispatch errors and raises an unexpected-response issue."""
    respx.post(_ALARMS).mock(return_value=Response(500, text="nope"))
    coordinator = _coordinator(hass, setup_entry)

    await coordinator.async_dispatch(["police"], 0)
    await hass.async_block_till_done()

    assert coordinator.data["state"] == STATE_ERROR
    assert _has_issue(hass, ISSUE_UNEXPECTED_RESPONSE, setup_entry.entry_id)
