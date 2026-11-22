"""Tests for the Daikin Onecta coordinator client adapter."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

from aiohttp import RequestInfo
from daikin_onecta import (
    OnectaApiError,
    OnectaAuthenticationError,
    OnectaClient,
    OnectaConnectionError,
    OnectaRateLimitError,
    Site,
)
from daikin_onecta.rate_limit import RateLimit
import pytest
from pytest_homeassistant.common import MockConfigEntry
from yarl import URL

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.util import dt as dt_util


async def test_get_device_details_propagates_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Propagate library connection errors to the coordinator."""
    with patch(
        "homeassistant.components.daikin_onecta.coordinator.OnectaClient.get_gateway_devices",
        new=AsyncMock(
            side_effect=OnectaConnectionError(
                "network unavailable",
                method="GET",
                path="/v1/gateway-devices",
            )
        ),
    ):
        api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
        with pytest.raises(OnectaConnectionError, match="network unavailable"):
            await api._async_get_cloud_devices()


async def test_access_token(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Return the OAuth access token after ensuring it is valid."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    api.session.async_ensure_token_valid = AsyncMock()
    with patch.object(
        type(api.session),
        "token",
        new_callable=lambda: property(lambda self: {"access_token": "token"}),
    ):
        assert await api.async_get_access_token() == "token"
    api.session.async_ensure_token_valid.assert_awaited_once()


async def test_get_device_details_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Propagate a library rate-limit error to the coordinator."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    api.client.get_gateway_devices = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60),
            method="GET",
            path="/v1/gateway-devices",
        )
    )

    with pytest.raises(OnectaRateLimitError):
        await api._async_get_cloud_devices()


async def test_get_sites(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fetch sites without using the normal polling endpoint."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    sites = [Site(id="site-1", gateway_device_ids=["gateway-1"])]
    api.client.get_sites = AsyncMock(return_value=sites)

    assert await api.async_get_sites() == sites
    api.client.get_sites.assert_awaited_once_with()


async def test_get_sites_rate_limit_sets_shared_backoff(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A Sites rate limit prevents later explicit cloud requests until retry."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    api.client.get_sites = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60), method="GET", path="/v1/sites"
        )
    )

    with pytest.raises(OnectaRateLimitError):
        await api.async_get_sites()

    assert api._polling_backoff_remaining() == timedelta(seconds=60)
    with pytest.raises(OnectaRateLimitError):
        await api.async_get_sites()
    api.client.get_sites.assert_awaited_once_with()


async def test_get_device_details_respects_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Do not fetch cloud data while a successful write is in its cooldown."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    api._last_patch_call = dt_util.utcnow()
    api.client.get_gateway_devices = AsyncMock()

    assert await api._async_get_cloud_devices() is None
    api.client.get_gateway_devices.assert_not_awaited()


async def test_get_device_details_always_respects_post_write_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Do not allow callers to bypass the post-write cooldown."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    api._last_patch_call = dt_util.utcnow()
    api.client.get_gateway_devices = AsyncMock(return_value=[])

    assert await api._async_get_cloud_devices() is None
    api.client.get_gateway_devices.assert_not_awaited()


@patch("homeassistant.components.daikin_onecta.coordinator.dt_util.utcnow")
async def test_get_device_details_uses_utc_across_dst_rollback(
    mock_utcnow: MagicMock,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """End cooldown based on elapsed time, not the local DST clock."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    # In Amsterdam, local time moves from 02:59 CEST back to 02:01 CET here.
    api._last_patch_call = datetime(2026, 10, 25, 0, 59, tzinfo=UTC)
    mock_utcnow.return_value = datetime(2026, 10, 25, 1, 1, tzinfo=UTC)
    api.client.get_gateway_devices = AsyncMock(return_value=[])

    assert await api._async_get_cloud_devices() == []
    api.client.get_gateway_devices.assert_awaited_once_with()


async def test_write_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Record successful writes."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock()

    assert await api.async_execute_command(command)
    command.assert_awaited_once_with(api.client)
    assert api._last_patch_call is not None


@pytest.mark.parametrize(
    ("status", "expected_reauth_count", "expected_log"),
    [
        pytest.param(401, 1, "failed authentication", id="unauthorized"),
        pytest.param(403, 0, "was not authorized", id="forbidden"),
    ],
)
async def test_write_authentication_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    status: int,
    expected_reauth_count: int,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only a 401 write authentication failure starts reauthentication."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock(
        side_effect=OnectaAuthenticationError(
            status=status,
            method="PATCH",
            path="/v1/management-points/point",
        )
    )

    with (
        caplog.at_level("DEBUG"),
        patch.object(config_entry, "async_start_reauth") as start_reauth,
    ):
        assert not await api.async_execute_command(command)

    assert start_reauth.call_args_list == [call(hass)] * expected_reauth_count
    assert hass.config_entries.flow.async_progress() == []
    assert api._last_patch_call is None
    assert (
        f"Daikin request PATCH /v1/management-points/point {expected_log} "
        f"with HTTP {status}" in caplog.text
    )


async def test_write_preserves_oauth_token_rejection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Propagate token-provider OAuth failures from the pinned client unchanged."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    url = URL("https://idp.onecta.daikineurope.com/v1/oidc/token")
    token_error = OAuth2TokenRequestReauthError(
        domain=config_entry.domain,
        request_info=RequestInfo(url=url, method="POST", headers={}, real_url=url),
        status=401,
        message="invalid_grant",
    )

    session = MagicMock()
    token_provider = AsyncMock(side_effect=token_error)
    api._client = OnectaClient(session, token_provider)

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "zone", "temperatureControl", 21)

    assert not await api.async_execute_command(command)

    token_provider.assert_awaited_once_with()
    session.request.assert_not_called()
    assert api._last_patch_call is None


async def test_write_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for API write failures."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock(
        side_effect=OnectaApiError(
            500, "failed", method="PATCH", path="/v1/management-points/point"
        )
    )

    assert not await api.async_execute_command(command)
    assert api._last_patch_call is None
    assert (
        "Daikin request PATCH /v1/management-points/point failed with HTTP 500"
        in caplog.text
    )


async def test_write_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for connection failures without recording a successful write."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock(
        side_effect=OnectaConnectionError(
            "network unavailable",
            method="PATCH",
            path="/v1/management-points/point",
        )
    )

    assert not await api.async_execute_command(command)
    assert api._last_patch_call is None
    assert (
        "Daikin request PATCH /v1/management-points/point failed to connect: "
        "network unavailable" in caplog.text
    )


async def test_write_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for rate-limited writes."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60),
            method="PATCH",
            path="/v1/management-points/point",
        )
    )

    assert not await api.async_execute_command(command)
    assert api._last_patch_call is None
    assert (
        "Daikin request PATCH /v1/management-points/point was rate limited; "
        "retry after 60 seconds" in caplog.text
    )


async def test_write_token_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false when refreshing the OAuth token fails during a write."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock(side_effect=OAuth2TokenRequestConnectionError(domain=DOMAIN))

    assert not await api.async_execute_command(command)
    assert api._last_patch_call is None
    assert "OAuth2TokenRequestConnectionError" in caplog.text


async def test_write_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false when a token refresh times out during a write."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock(side_effect=TimeoutError)

    assert not await api.async_execute_command(command)
    assert api._last_patch_call is None
    assert "Daikin request timed out" in caplog.text


async def test_unknown_rate_limit_uses_default_polling_budget(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Use the conservative polling budget when response headers are absent."""
    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.client.rate_limit = RateLimit()
    assert coordinator._polling_intervals() == (
        timedelta(seconds=594),
        timedelta(seconds=1782),
    )


async def test_rate_limits_preserve_unknown_values(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep rate-limit values unavailable when Daikin did not send them."""
    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.client.rate_limit = RateLimit()

    assert coordinator.rate_limits == {
        "minute": None,
        "day": None,
        "remaining_minutes": None,
        "remaining_day": None,
        "retry_after": None,
        "ratelimit_reset": None,
    }
