"""Tests for async_setup_entry() in __init__.py."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bluetti.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError

from tests.common import MockConfigEntry


def _entry(hass: HomeAssistant, *, products=None, devices=None) -> MockConfigEntry:
    options = {"devices": devices or []}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "products": products or [],
        },
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def test_async_setup_entry_with_no_devices(hass: HomeAssistant) -> None:
    """Async setup entry with no devices."""
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.bluetti_devices.devices == []
    assert entry.runtime_data.coordinators == {}
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_async_setup_entry_recovers_missing_default_credential(
    hass: HomeAssistant,
) -> None:
    """Setup recovers a restored entry whose Application Credentials storage is missing.

    Regression test: async_ensure_default_credential() was only called from
    the config flow, never from async_setup_entry, despite its own
    docstring promising it runs "on every setup" - a restored entry with no
    Application Credentials entry would otherwise fail
    async_get_config_entry_implementation() and stay in ConfigEntryNotReady
    retry forever.
    """
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.async_ensure_default_credential",
            AsyncMock(),
        ) as mock_ensure_credential,
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_ensure_credential.assert_awaited_once_with(hass)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.homeassistant.issues.config_entry_reauth.title",
            "component.homeassistant.issues.config_entry_reauth.description",
        ]
    ],
)
async def test_async_setup_entry_classifies_reauth_error_as_auth_failed(
    hass: HomeAssistant,
) -> None:
    """An invalid/revoked refresh token must trigger reauth, not endless retries.

    Regression test: a broad `except Exception` around
    oauth_session.async_ensure_token_valid() used to wrap
    OAuth2TokenRequestReauthError (raised when the refresh token itself is
    invalid) into ConfigEntryNotReady, which schedules infinite setup
    retries that would fail identically every time instead of surfacing
    the standard reauth flow via ConfigEntryAuthFailed.
    """
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
    ):
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock(
            side_effect=OAuth2TokenRequestReauthError(
                domain=DOMAIN, request_info=MagicMock()
            )
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_with_an_expired_but_refreshable_token_does_not_notify(
    hass: HomeAssistant,
) -> None:
    """An expired-but-refreshable token must not show a false expiry warning.

    Regression test: AuthTokenRefresh.start_token_check() used to run before
    oauth_session.async_ensure_token_valid() - its is_token_valid() check
    read the stale, not-yet-refreshed token, so a normally expired access
    token (common - they're short-lived) with a still-valid refresh token
    triggered a persistent notification/issue immediately, moments before
    async_ensure_token_valid() transparently fixed the token.
    """
    entry = _entry(hass)

    async def fake_ensure_token_valid():
        # Simulates a successful refresh: the session's token is updated in
        # place, same as the real OAuth2Session.async_ensure_token_valid().
        mock_session_cls.return_value.token = {
            "access_token": "refreshed",
            "expires_at": time.time() + 10000,
        }

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti.oauth.persistent_notification.async_create"
        ) as mock_notify,
    ):
        # Starts expired (in the past) - is_token_valid() must see the
        # already-refreshed token above, not this one, by the time
        # AuthTokenRefresh.start_token_check() runs.
        mock_session_cls.return_value.token = {
            "access_token": "stale",
            "expires_at": time.time() - 100,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock(
            side_effect=fake_ensure_token_valid
        )
        mock_stomp_cls.return_value.connect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    mock_notify.assert_not_called()


async def test_setup_succeeds_and_rest_coordinator_runs_when_websocket_unavailable(
    hass: HomeAssistant,
) -> None:
    """The REST polling coordinator must work even if the WebSocket never connects.

    Regression coverage for the fix that made stomp_client.connect() a
    background task instead of an inline await: a real, permanently
    unreachable WSS endpoint means pybluetti's StompClient.connect() never
    returns (it retries with its own growing exponential backoff, awaiting
    itself again on every failure - see reconnect()) - simulated here with
    an AsyncMock that never resolves. Before that fix, awaiting connect()
    directly would have hung this whole test (and, for real, the whole
    config entry setup) instead of asserting anything.
    """
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    async def _never_connects() -> None:
        await asyncio.Event().wait()  # never set - simulates an endpoint
        # that's never reachable, matching StompClient's real retry-forever
        # behavior on a permanent failure.

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock(side_effect=_never_connects)
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        # Deliberately not wait_background_tasks=True here: that would wait
        # for the never-resolving connect() task too, hanging this test -
        # exactly the point being verified is that setup doesn't need to.
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert "SN1" in entry.runtime_data.coordinators
    assert entry.runtime_data.coordinators["SN1"].last_update_success


async def test_async_setup_entry_with_a_device(hass: HomeAssistant) -> None:
    """Async setup entry with a device."""
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    devices = entry.runtime_data.bluetti_devices.devices
    assert len(devices) == 1
    assert devices[0].device_id == "SN1"
    assert "SN1" in entry.runtime_data.coordinators
    mock_stomp_cls.return_value.connect.assert_awaited_once()


async def test_async_setup_entry_with_multiple_devices_refreshes_concurrently(
    hass: HomeAssistant,
) -> None:
    """Async setup entry with multiple devices refreshes concurrently."""
    # Each device's first refresh is run via asyncio.gather() instead of
    # sequentially, so setup time doesn't scale linearly with device count.
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Device 1", "stateList": [], "online": "1"},
            {"sn": "SN2", "name": "Device 2", "stateList": [], "online": "1"},
        ],
        devices=["SN1", "SN2"],
    )
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert set(coordinators.keys()) == {"SN1", "SN2"}
    assert all(c.last_update_success for c in coordinators.values())


async def test_one_device_failing_first_refresh_does_not_orphan_the_others(
    hass: HomeAssistant,
) -> None:
    """A failing device's first refresh must not leave others as orphaned tasks.

    Regression test: asyncio.gather() without return_exceptions=True
    propagates the first exception as soon as it happens, without waiting
    for (or cancelling) the other coordinators' still-in-flight first
    refreshes - they kept running as untracked background tasks that could
    still mutate state after setup had already moved on to SETUP_RETRY.
    SN2 fails immediately; SN1 is deliberately slower, so if it were left
    running unawaited, hass.config_entries.async_setup() would return
    before SN1's own refresh actually completed.
    """
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Device 1", "stateList": [], "online": "1"},
            {"sn": "SN2", "name": "Device 2", "stateList": [], "online": "1"},
        ],
        devices=["SN1", "SN2"],
    )
    sn1_refresh_completed = asyncio.Event()

    async def fake_get_device_status(sn):
        if sn == "SN2":
            raise RuntimeError("boom")
        await asyncio.sleep(0.05)
        sn1_refresh_completed.set()
        return MagicMock(
            data=[MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])]
        )

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)

    # By the time async_setup() has returned, SN1's slower refresh must
    # have already completed too - not left running unawaited.
    assert sn1_refresh_completed.is_set()


async def test_device_unbound_during_first_refresh_is_not_set_up(
    hass: HomeAssistant,
) -> None:
    """A device unbound during its own first refresh must not still load.

    Regression test: entry.runtime_data used to be assigned after the
    first-refresh gather, not before - a device reporting
    isBindByCurUser="0" on that very first refresh triggers
    _handle_unbind(), which needs runtime_data to exist to remove the
    device from bluetti_devices/coordinators. With no runtime_data yet,
    that step silently did nothing, and the device was set up anyway once
    runtime_data was assigned right after - even though its device/entity
    registry entries had just been deleted by the same _handle_unbind()
    call.
    """
    entry = _entry(
        hass,
        products=[
            {"sn": "SN1", "name": "Device 1", "stateList": [], "online": "1"},
            {"sn": "SN2", "name": "Device 2", "stateList": [], "online": "1"},
        ],
        devices=["SN1", "SN2"],
    )
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="0", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
        patch(
            "homeassistant.components.bluetti.models.persistent_notification.async_create"
        ),
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert "SN1" not in entry.runtime_data.coordinators
    assert "SN2" in entry.runtime_data.coordinators
    assert [d.device_id for d in entry.runtime_data.bluetti_devices.devices] == ["SN2"]

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.options["devices"] == ["SN2"]


async def test_async_setup_entry_retries_on_failure(hass: HomeAssistant) -> None:
    """Async setup entry retries on failure."""
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unloading_the_entry_disconnects_the_websocket(
    hass: HomeAssistant,
) -> None:
    """Unloading the entry disconnects the websocket."""
    entry = _entry(hass)

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_stomp_cls.return_value.disconnect.assert_awaited_once()


async def test_a_failed_first_refresh_still_disconnects_the_websocket(
    hass: HomeAssistant,
) -> None:
    """A failed first refresh still disconnects the websocket, not just a full unload.

    Regression test: the websocket's disconnect must be registered via
    entry.async_on_unload() as soon as it connects, not only handled
    explicitly in async_unload_entry() - otherwise a first refresh failure
    (which puts the entry into a setup retry, not a full unload) would leave
    that websocket connection open, and each retry would connect a new one
    without ever disconnecting the last.
    """
    entry = _entry(
        hass,
        products=[{"sn": "SN1", "name": "Device", "stateList": [], "online": "1"}],
        devices=["SN1"],
    )

    with (
        patch("homeassistant.components.bluetti.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti.StompClient") as mock_stomp_cls,
        patch("homeassistant.components.bluetti.ProductClient") as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=RuntimeError("cloud is down")
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_stomp_cls.return_value.disconnect.assert_awaited_once()
