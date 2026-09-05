"""Full config-flow coverage via a real HomeAssistant instance.

Drives ``TrueNASConfigFlow`` through ``hass.config_entries.flow`` to cover the
user/zeroconf steps end to end.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import ipaddress
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.truenas_ce import config_flow
from homeassistant.components.truenas_ce.const import (
    CONF_DATA_UNIT,
    CONF_SYSTEM_ID,
    DEFAULT_DATA_UNIT,
    DEFAULT_HOST,
    DOMAIN,
    ERR_CONNECTION_REFUSED,
    ERR_INVALID_KEY,
    ERR_TIMEOUT,
)
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

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
    """A second entry for the same box (different host) must not be created.

    The user-flow host-uniqueness guard alone would miss this, since the new
    entry uses a different host; the system_id-based unique_id check must
    catch it instead. The existing entry's host is folded onto the new one
    (see ``test_zeroconf_flow_updates_matched_entry_host_after_user_authenticates``
    for the equivalent zeroconf-triggered case), since re-adding it here only
    succeeded because the user supplied a real, working API key for it.
    """
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


# ---------------------------
#   zeroconf step
# ---------------------------
def _zeroconf_discovery_info(host: str = "192.168.1.50") -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address(host),
        ip_addresses=[ipaddress.ip_address(host)],
        port=80,
        hostname="truenas.local.",
        type="_http._tcp.local.",
        name="truenas._http._tcp.local.",
        properties={},
    )


async def test_async_probe_candidate_true_on_rejected_bogus_key() -> None:
    """A rejected bogus key proves a genuine TrueNAS endpoint.

    Regression test: connect() reports a rejected key as False plus
    api.error == ERR_INVALID_KEY, not as a truthy return value; the probe
    must still detect this as "this is TrueNAS" instead of "unreachable".
    """

    async def _fake_connect(
        self: config_flow.TrueNASAPI, *, quiet: bool = False
    ) -> bool:
        self._error = ERR_INVALID_KEY
        return False

    with (
        patch(f"{_API_PATH}.connect", _fake_connect),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        assert await config_flow._async_probe_candidate("192.168.1.50") is True


async def test_async_probe_candidate_false_when_unreachable() -> None:
    """A candidate that never completes the handshake is not mistaken for TrueNAS."""

    async def _fake_connect(
        self: config_flow.TrueNASAPI, *, quiet: bool = False
    ) -> bool:
        self._error = ERR_CONNECTION_REFUSED
        return False

    with (
        patch(f"{_API_PATH}.connect", _fake_connect),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        assert await config_flow._async_probe_candidate("192.168.1.50") is False


async def test_zeroconf_flow_confirms_and_creates_entry(hass: HomeAssistant) -> None:
    """A confirmed zeroconf discovery proceeds to the user step and creates an entry."""
    with patch.object(
        config_flow.TrueNASConfigFlow,
        "_probe_is_truenas",
        AsyncMock(return_value="192.168.1.50"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info(),
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {CONF_HOST: "192.168.1.50"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(return_value=None)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input(**{CONF_HOST: "192.168.1.50"})
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.50"


async def test_zeroconf_flow_brackets_ipv6_host(hass: HomeAssistant) -> None:
    """A bare IPv6 discovery address is bracketed before being probed.

    Regression test: ``ZeroconfServiceInfo.host`` is the raw, unbracketed
    IPv6 literal; passing it straight through would build a malformed
    WebSocket URL (see ``helper.sanitize_host``).
    """
    with patch.object(
        config_flow.TrueNASConfigFlow,
        "_probe_is_truenas",
        AsyncMock(return_value="[2001:db8::1]"),
    ) as mock_probe:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info("2001:db8::1"),
        )
    assert mock_probe.call_args.args[0] == "[2001:db8::1]"
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_HOST: "[2001:db8::1]"}


async def test_zeroconf_flow_keeps_advertised_port(hass: HomeAssistant) -> None:
    """A box found only on its advertised port is configured with that port."""
    with patch.object(
        config_flow.TrueNASConfigFlow,
        "_probe_is_truenas",
        AsyncMock(return_value="192.168.1.50:8443"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info(),
        )
    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {CONF_HOST: "192.168.1.50:8443"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(return_value=None)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _user_input(**{CONF_HOST: "192.168.1.50:8443"})
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.50:8443"


async def test_zeroconf_flow_aborts_when_not_truenas(hass: HomeAssistant) -> None:
    """The zeroconf flow aborts when the probe cannot confirm a TrueNAS box."""
    with patch.object(
        config_flow.TrueNASConfigFlow,
        "_probe_is_truenas",
        AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info(),
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_truenas"


async def test_zeroconf_flow_aborts_on_already_configured_host(
    hass: HomeAssistant,
) -> None:
    """A zeroconf discovery matching an existing entry's host is aborted."""
    existing = MockConfigEntry(
        domain=DOMAIN, data=_user_input(**{CONF_HOST: "192.168.1.50"})
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_zeroconf_discovery_info(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow_never_probes_stored_credentials(
    hass: HomeAssistant,
) -> None:
    """Discovery must never replay an existing entry's stored API key.

    Regression test for a credential-leak: the flow used to try every
    configured entry's real API key against a host that only had to mimic a
    tiny probe handshake to be treated as "confirmed TrueNAS" -- a spoofed
    LAN device could harvest every stored key that way. Now a probed host
    always falls through to the user-facing confirm step instead, so the
    entry's real (unrelated) key must never even be constructed against the
    newly discovered host.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="shared-id",
        data=_user_input(
            **{
                CONF_HOST: "old-host.example.com",
                CONF_API_KEY: "existing-real-key",
                CONF_SYSTEM_ID: "shared-id",
            }
        ),
    )
    entry.add_to_hass(hass)

    with (
        patch.object(
            config_flow.TrueNASConfigFlow,
            "_probe_is_truenas",
            AsyncMock(return_value="192.168.1.50"),
        ),
        patch(f"{_API_PATH}.__init__", return_value=None) as mock_init,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info(),
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    mock_init.assert_not_called()
    assert entry.data[CONF_HOST] == "old-host.example.com"


async def test_zeroconf_flow_updates_matched_entry_host_after_user_authenticates(
    hass: HomeAssistant,
) -> None:
    """A rediscovered box's host is folded into its matching entry.

    But only once *this* flow has itself authenticated the box and confirmed
    its real system_id, not by trusting the discovery broadcast or replaying
    a stored credential (see
    ``test_zeroconf_flow_never_probes_stored_credentials``).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="shared-id",
        data=_user_input(
            **{CONF_HOST: "old-host.example.com", CONF_SYSTEM_ID: "shared-id"}
        ),
    )
    entry.add_to_hass(hass)

    _query_responses = {
        "system.global.id": "shared-id",
        "system.info": {"hostname": "renamed-box"},
    }

    async def _query(method: str, *args: object, **kwargs: object) -> object:
        return _query_responses.get(method)

    with patch.object(
        config_flow.TrueNASConfigFlow,
        "_probe_is_truenas",
        AsyncMock(return_value="192.168.1.50"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info(),
        )
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "user"

    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(side_effect=_query)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _user_input(
                **{CONF_HOST: "192.168.1.50", CONF_API_KEY: "freshly-typed-key"}
            ),
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.50"
    assert entry.unique_id == "shared-id"


async def test_zeroconf_flow_creates_new_entry_when_system_id_does_not_match(
    hass: HomeAssistant,
) -> None:
    """A rediscovered host with a different real system_id gets its own entry.

    Guards against merging into the wrong entry: an unrelated existing entry
    must be left untouched when the newly (user-authenticated) confirmed box
    turns out to be a different physical device.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="old-id",
        data=_user_input(
            **{
                CONF_HOST: "old-host.example.com",
                CONF_SYSTEM_ID: "old-id",
                CONF_NAME: "existing-box",
            }
        ),
    )
    entry.add_to_hass(hass)

    _query_responses = {
        "system.global.id": "different-id",
        "system.info": {"hostname": "new-box"},
    }

    async def _query(method: str, *args: object, **kwargs: object) -> object:
        return _query_responses.get(method)

    with patch.object(
        config_flow.TrueNASConfigFlow,
        "_probe_is_truenas",
        AsyncMock(return_value="192.168.1.50"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=_zeroconf_discovery_info(),
        )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    with (
        patch(f"{_API_PATH}.connection_test", AsyncMock(return_value=(True, None))),
        patch(f"{_API_PATH}.query", AsyncMock(side_effect=_query)),
        patch(f"{_API_PATH}.disconnect", AsyncMock(return_value=None)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _user_input(
                **{CONF_HOST: "192.168.1.50", CONF_API_KEY: "freshly-typed-key"}
            ),
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.50"
    assert entry.data[CONF_HOST] == "old-host.example.com"
    assert entry.unique_id == "old-id"
    assert entry.data[CONF_SYSTEM_ID] == "old-id"
    new_entry = hass.config_entries.async_get_entry(result["result"].entry_id)
    assert new_entry is not None
    assert new_entry.unique_id == "different-id"
    assert new_entry.unique_id != entry.unique_id
