"""Full config-flow coverage via a real HomeAssistant instance.

Drives ``TrueNASConfigFlow`` through ``hass.config_entries.flow`` to cover the
user step end to end.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.truenas_ce.const import (
    CONF_DATA_UNIT,
    CONF_SYSTEM_ID,
    DEFAULT_DATA_UNIT,
    DEFAULT_HOST,
    DOMAIN,
    ERR_INVALID_KEY,
    ERR_TIMEOUT,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

_API_PATH = "homeassistant.components.truenas_ce.config_flow.TrueNASAPI"


def _user_input(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        CONF_HOST: "truenas.example.com",
        CONF_API_KEY: "test-key",
        CONF_VERIFY_SSL: False,
        CONF_DATA_UNIT: DEFAULT_DATA_UNIT,
    } | overrides
    return data


@pytest.fixture(autouse=True)
def _mock_setup_entry() -> Iterator[AsyncMock]:
    """Prevent a real integration setup from running during flow tests."""
    with patch(
        "homeassistant.components.truenas_ce.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(autouse=True)
def _mock_guess_ip() -> Iterator[None]:
    """Avoid the DNS lookup the test harness forbids.

    ``async_step_user`` calls ``_guess_ip()`` (a real ``socket.gethostbyname``
    lookup) to prefill a default host; the test harness patches
    ``socket.gethostbyname`` to raise for any non-local/non-IP hostname.
    """
    with patch(
        "homeassistant.components.truenas_ce.config_flow._guess_ip",
        return_value=DEFAULT_HOST,
    ):
        yield


@pytest.fixture
def _mock_connection_ok() -> Iterator[None]:
    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(return_value=None)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        yield


@contextmanager
def _mock_connection_failure(errorcode: str) -> Iterator[None]:
    """Patch connection_test to fail with errorcode; disconnect stays a no-op."""
    with (
        patch(
            f"{_API_PATH}.connection_test",
            AsyncMock(return_value=(False, errorcode)),
        ),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        yield


# ---------------------------
#   user step
# ---------------------------
@pytest.mark.usefixtures("_mock_connection_ok")
async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """The user flow creates a config entry from the submitted host data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TrueNAS"
    assert result["data"][CONF_HOST] == "truenas.example.com"
    # The data-unit display preference isn't needed to connect, so it belongs
    # in options (mutable later) rather than the immutable connection data.
    assert CONF_DATA_UNIT not in result["data"]
    assert result["options"][CONF_DATA_UNIT] == DEFAULT_DATA_UNIT


async def test_user_flow_creates_entry_with_system_id_as_unique_id(
    hass: HomeAssistant,
) -> None:
    """Once the box's stable identity is known it becomes the entry's unique_id."""
    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(return_value="box-guid-123")),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SYSTEM_ID] == "box-guid-123"
    entry = hass.config_entries.async_get_entry(result["result"].entry_id)
    assert entry is not None
    assert entry.unique_id == "box-guid-123"


async def test_user_flow_aborts_on_duplicate_system_id(hass: HomeAssistant) -> None:
    """A second entry for the same box (different host) aborts, folding the host onto the existing entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=_user_input(**{CONF_HOST: "old-host.example.com"}),
        unique_id="box-guid-123",
    )
    existing.add_to_hass(hass)

    # A distinct hostname (for system.info) so the auto-derived name never
    # collides with the existing entry's, keeping this test focused on the
    # system_id-based dedup rather than the unrelated name check.
    _query_responses = {
        "system.global.id": "box-guid-123",
        "system.info": {"hostname": "new-host"},
    }

    async def _query(method: str, *args: object, **kwargs: object) -> object:
        return _query_responses.get(method)

    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(side_effect=_query)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _user_input(**{CONF_HOST: "new-host.example.com"}),
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert existing.data[CONF_HOST] == "new-host.example.com"


async def test_user_flow_allows_duplicate_name_for_distinct_host(
    hass: HomeAssistant,
) -> None:
    """Two different devices whose auto-derived name collides may both be added.

    Real duplicate-device protection is host/system_id based (see the
    duplicate-host test below), so a name collision alone must not block
    setup. The name is not user-chosen (see _async_get_hostname), so this
    exercises the case where system.info carries no usable hostname for
    either box and both fall back to the same DEFAULT_DEVICE_NAME. This is
    safe at the entity layer too: unique_ids/device identifiers are keyed on
    CONF_SYSTEM_ID/entry_id, not this display name (see
    entity.resolve_entry_identity and its dedicated tests).
    """
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=_user_input(**{CONF_HOST: "other-host.example.com", CONF_NAME: "TrueNAS"}),
    )
    existing.add_to_hass(hass)

    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(return_value=None)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_aborts_on_duplicate_host(hass: HomeAssistant) -> None:
    """A second entry for the same host is aborted as already configured."""
    existing = MockConfigEntry(domain=DOMAIN, data=_user_input())
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _user_input()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_connection_error_maps_to_ha_error(hass: HomeAssistant) -> None:
    """A failed connection surfaces the mapped error code on the host field."""
    with _mock_connection_failure(ERR_INVALID_KEY):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: ERR_INVALID_KEY}

    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(return_value=None)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_timeout_error_maps_to_ha_error(hass: HomeAssistant) -> None:
    """A connection timeout surfaces its own error code, not the generic fallback."""
    with _mock_connection_failure(ERR_TIMEOUT):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: ERR_TIMEOUT}


async def test_user_flow_shows_unknown_error_when_connection_test_raises(
    hass: HomeAssistant,
) -> None:
    """An unexpected exception from connection_test() degrades to a retryable error.

    _validate_connection() previously let such an exception propagate out of
    the flow entirely (crashing it with an unhandled traceback) instead of
    showing the user a normal, retryable "unknown" form error -- inconsistent
    with every other connection helper here, which already catches and logs
    broadly. It must also still disconnect, so the socket isn't leaked.
    """
    disconnect = AsyncMock(return_value=None)
    with (
        patch(
            f"{_API_PATH}.connection_test",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(f"{_API_PATH}.disconnect", disconnect),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input()
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "unknown"}
    disconnect.assert_awaited_once()
