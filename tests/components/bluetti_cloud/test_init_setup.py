"""Tests for async_setup_entry() in __init__.py."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pybluetti import UnifyResponse, UserProduct

from homeassistant.components.bluetti_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError

from tests.common import MockConfigEntry


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
        },
    )
    entry.add_to_hass(hass)
    return entry


def _products_response(products: list[UserProduct]) -> SimpleNamespace:
    return SimpleNamespace(data=products, is_ok=lambda: True)


async def test_async_setup_entry_with_no_devices(hass: HomeAssistant) -> None:
    """Async setup entry with no devices."""
    entry = _entry(hass)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response([])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.bluetti_devices.devices == []
    assert entry.runtime_data.coordinators == {}
    assert entry.data["device_sns"] == []
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
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.async_ensure_default_credential",
            AsyncMock(),
        ) as mock_ensure_credential,
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response([])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_ensure_credential.assert_awaited_once_with(hass)
    assert entry.state is ConfigEntryState.LOADED


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
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
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


async def test_auth_expired_during_initial_product_fetch_starts_reauth(
    hass: HomeAssistant,
) -> None:
    """An auth-expired signal fired during the very first product fetch still starts reauth.

    Regression test: AuthTokenRefresh (which registers the dispatcher
    listener for the auth-expired signal) used to be constructed only
    after get_user_products() had already succeeded - an auth-expired
    callback fired during that very first call had no listener yet and
    was silently dropped, leaving the entry stuck retrying via
    ConfigEntryNotReady instead of starting reauth.
    """
    entry = _entry(hass)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
        patch.object(entry, "async_start_reauth_if_available") as mock_start_reauth,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()

        async def fail_with_auth_expired(*args, **kwargs):
            # Mirrors what pybluetti's real Bluetti._request() does on a
            # msgCode 805 response: invoke on_auth_expired, then surface
            # the failure to the caller - get_user_products() itself
            # doesn't raise on a rejected envelope, it returns is_ok()=False.
            mock_product_cls.call_args.kwargs["on_auth_expired"]()
            return SimpleNamespace(data=None, is_ok=lambda: False)

        mock_product_cls.return_value.get_user_products = AsyncMock(
            side_effect=fail_with_auth_expired
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_start_reauth.assert_called_once_with(hass)


async def test_setup_fetches_products_fresh_not_from_a_stored_cache(
    hass: HomeAssistant,
) -> None:
    """Batteries included: the device list always comes from a fresh cloud fetch."""
    entry = _entry(hass)
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_product_cls.return_value.get_user_products.assert_awaited_once()
    assert entry.data["device_sns"] == ["SN1"]
    assert [d.device_id for d in entry.runtime_data.bluetti_devices.devices] == ["SN1"]


async def test_reconciliation_binds_only_a_newly_seen_device(
    hass: HomeAssistant,
) -> None:
    """A device added on the cloud side since the last setup gets bound.

    Regression test: setup used to persist the refreshed device_sns
    fingerprint without ever calling bind_devices() for a serial that
    wasn't there last time, so a device added after the entry's initial
    setup could be polled over REST but never receive WebSocket push
    updates (never bound). Only the newly-seen serial is bound, not the
    one already known.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "device_sns": ["SN1"],
        },
    )
    entry.add_to_hass(hass)
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [
                    UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
                    UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
                ]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_product_cls.return_value.bind_devices.assert_awaited_once_with(
        {"bindSnList": ["SN2"]}
    )
    assert entry.data["device_sns"] == ["SN1", "SN2"]


async def test_reconciliation_bind_failure_is_logged_not_fatal(
    hass: HomeAssistant,
) -> None:
    """A newly-seen device that fails to bind must not fail the whole setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {"access_token": "tok", "expires_at": time.time() + 10000},
            "device_sns": [],
        },
    )
    entry.add_to_hass(hass)
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=1)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            return_value=MagicMock(data=[status_data])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_product_cls.return_value.bind_devices.assert_awaited_once()
    assert entry.state is ConfigEntryState.LOADED


async def test_get_user_products_failure_retries_setup(hass: HomeAssistant) -> None:
    """A failed product fetch is a transient setup failure, not fatal."""
    entry = _entry(hass)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_product_cls.return_value.get_user_products = AsyncMock(
            side_effect=RuntimeError("boom")
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_user_products_rejected_envelope_retries_setup(
    hass: HomeAssistant,
) -> None:
    """A failed application-level response must not look like "no devices".

    Regression test: get_user_products() doesn't raise for a nonzero
    msgCode (e.g. an expired token) - it returns a response with
    is_ok() == False and data=None.
    """
    entry = _entry(hass)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=SimpleNamespace(data=None, is_ok=lambda: False)
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


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
    entry = _entry(hass)
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    async def _never_connects() -> None:
        await asyncio.Event().wait()  # never set - simulates an endpoint
        # that's never reachable, matching StompClient's real retry-forever
        # behavior on a permanent failure.

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock(side_effect=_never_connects)
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
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
    entry = _entry(hass)
    status_data = MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
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
    entry = _entry(hass)
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [
                    UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
                    UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
                ]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert set(coordinators.keys()) == {"SN1", "SN2"}
    assert all(c.last_update_success for c in coordinators.values())


async def test_one_device_failing_first_refresh_does_not_block_the_others(
    hass: HomeAssistant,
) -> None:
    """A failing device's first refresh must not prevent the others from loading.

    Regression test: any first-refresh failure used to fail the whole
    entry (ConfigEntryNotReady), even though the other devices' refreshes
    had already succeeded - one offline inverter took the entire account
    down instead of just starting unavailable on its own.
    """
    entry = _entry(hass)
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
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [
                    UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
                    UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
                ]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    coordinators = entry.runtime_data.coordinators
    assert coordinators["SN1"].last_update_success
    assert not coordinators["SN2"].last_update_success
    assert sn1_refresh_completed.is_set()


async def test_shared_auth_failure_during_first_refresh_fails_the_whole_entry(
    hass: HomeAssistant,
) -> None:
    """An auth failure on one device's first refresh applies to every device.

    Unlike a plain per-device failure, the OAuth token is shared by the
    whole account - one device reporting it invalid means they all are, so
    this must still surface as ConfigEntryAuthFailed for the entire entry.
    """
    entry = _entry(hass)

    async def fake_get_device_status(sn):
        if sn == "SN2":
            return MagicMock(
                is_ok=lambda: False,
                msgCode=401,
                data=None,
            )
        return MagicMock(
            data=[MagicMock(sn="SN1", isBindByCurUser="1", online="1", stateList=[])]
        )

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [
                    UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
                    UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
                ]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_ERROR


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
    entry = _entry(hass)
    status_data = {
        "SN1": MagicMock(sn="SN1", isBindByCurUser="0", online="1", stateList=[]),
        "SN2": MagicMock(sn="SN2", isBindByCurUser="1", online="1", stateList=[]),
    }

    async def fake_get_device_status(sn):
        return MagicMock(data=[status_data[sn]])

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
        patch(
            "homeassistant.components.bluetti_cloud.models.persistent_notification.async_create"
        ),
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [
                    UserProduct(sn="SN1", name="Device 1", stateList=[], online="1"),
                    UserProduct(sn="SN2", name="Device 2", stateList=[], online="1"),
                ]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert "SN1" not in entry.runtime_data.coordinators
    assert "SN2" in entry.runtime_data.coordinators
    assert [d.device_id for d in entry.runtime_data.bluetti_devices.devices] == ["SN2"]


async def test_async_setup_entry_retries_on_failure(hass: HomeAssistant) -> None:
    """Async setup entry retries on failure."""
    entry = _entry(hass)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
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
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response([])
        )

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_stomp_cls.return_value.disconnect.assert_awaited_once()


async def test_a_failed_setup_still_disconnects_the_websocket(
    hass: HomeAssistant,
) -> None:
    """A setup that fails after the websocket connects still disconnects it.

    Regression test: the websocket's disconnect must be registered via
    entry.async_on_unload() as soon as it connects, not only handled
    explicitly in async_unload_entry() - otherwise a setup failure (which
    puts the entry into a setup retry/error, not a full unload) would leave
    that websocket connection open, and each retry would connect a new one
    without ever disconnecting the last. A shared-auth failure during first
    refresh is used here since it's the one first-refresh failure that
    still fails the whole entry after the websocket has already connected.
    """
    entry = _entry(hass)

    async def fake_get_device_status(sn):
        return MagicMock(is_ok=lambda: False, msgCode=401, data=None)

    with (
        patch(
            "homeassistant.components.bluetti_cloud.async_get_clientsession",
            MagicMock(),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.bluetti_cloud.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session_cls,
        patch("homeassistant.components.bluetti_cloud.StompClient") as mock_stomp_cls,
        patch(
            "homeassistant.components.bluetti_cloud.ProductClient"
        ) as mock_product_cls,
    ):
        mock_session_cls.return_value.token = {
            "access_token": "tok",
            "expires_at": time.time() + 10000,
        }
        mock_session_cls.return_value.async_ensure_token_valid = AsyncMock()
        mock_session_cls.return_value.implementation.async_refresh_token = AsyncMock(
            return_value={"access_token": "tok", "expires_at": time.time() + 10000}
        )
        mock_stomp_cls.return_value.connect = AsyncMock()
        mock_stomp_cls.return_value.disconnect = AsyncMock()
        mock_product_cls.return_value.get_user_products = AsyncMock(
            return_value=_products_response(
                [UserProduct(sn="SN1", name="Device", stateList=[], online="1")]
            )
        )
        mock_product_cls.return_value.bind_devices = AsyncMock(
            return_value=UnifyResponse(msgId="1", msgCode=0)
        )
        mock_product_cls.return_value.get_device_status = AsyncMock(
            side_effect=fake_get_device_status
        )

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_stomp_cls.return_value.disconnect.assert_awaited_once()
