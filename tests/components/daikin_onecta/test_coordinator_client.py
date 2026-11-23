"""Tests for the Daikin Onecta coordinator client adapter."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from aiohttp import RequestInfo
from daikin_onecta import (
    OnectaApiError,
    OnectaClient,
    OnectaConnectionError,
    OnectaRateLimitError,
    Site,
)
from daikin_onecta.rate_limit import RateLimit
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
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

from .conftest import FAKE_ACCESS_TOKEN, MockOnectaClient
from .platform_helpers import _async_setup_fixture


async def test_get_device_details_propagates_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Propagate library connection errors to the coordinator."""
    mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
        "network unavailable", method="GET", path="/v1/gateway-devices"
    )
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    with pytest.raises(OnectaConnectionError, match="network unavailable"):
        await api._async_get_cloud_devices()


async def test_access_token(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Return the OAuth access token after ensuring it is valid."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    assert await api.async_get_access_token() == FAKE_ACCESS_TOKEN


async def test_get_device_details_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Propagate a library rate-limit error to the coordinator."""
    mock_onecta_client.get_gateway_devices.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
    )
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())

    with pytest.raises(OnectaRateLimitError):
        await api._async_get_cloud_devices()


async def test_get_sites(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Fetch sites without using the normal polling endpoint."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    sites = [Site(id="site-1", gateway_device_ids=["gateway-1"])]
    mock_onecta_client.get_sites.return_value = sites

    assert await api.async_get_sites() == sites
    mock_onecta_client.get_sites.assert_awaited_once_with()


async def test_get_sites_rate_limit_sets_shared_backoff(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A Sites rate limit prevents later explicit cloud requests until retry."""
    mock_onecta_client.get_sites.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=60), method="GET", path="/v1/sites"
    )
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())

    with pytest.raises(OnectaRateLimitError):
        await api.async_get_sites()

    with pytest.raises(OnectaRateLimitError):
        await api.async_get_sites()
    mock_onecta_client.get_sites.assert_awaited_once_with()


async def test_scheduled_poll_respects_write_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep scheduled polling within the write cooldown out of the cloud."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    api = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.reset_mock()
    freezer.tick(api.update_interval - timedelta(seconds=1))
    assert await api.async_execute_command(AsyncMock())
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_onecta_client.get_gateway_devices.assert_not_awaited()


async def test_get_device_details_uses_elapsed_utc_time(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Fetch after the post-write cooldown expires across a DST transition."""
    freezer.move_to(datetime(2026, 10, 25, 0, 59, tzinfo=UTC))
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    api = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.reset_mock()
    api.schedule_post_write_refresh()
    assert await api.async_execute_command(AsyncMock())
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_onecta_client.get_gateway_devices.assert_awaited_once_with()


async def test_write_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Record successful writes."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    command = AsyncMock()

    assert await api.async_execute_command(command)
    command.assert_awaited_once_with(api.client)


async def test_write_preserves_oauth_token_rejection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Propagate token-provider OAuth failures from the pinned client unchanged."""
    api = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    token_url = URL("https://idp.onecta.daikineurope.com/v1/oidc/token")
    token_error = OAuth2TokenRequestReauthError(
        domain=config_entry.domain,
        request_info=RequestInfo(
            url=token_url, method="POST", headers={}, real_url=token_url
        ),
        status=401,
        message="invalid_grant",
    )
    mock_onecta_client.patch_characteristic.side_effect = token_error

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "zone", "temperatureControl", 21)

    assert not await api.async_execute_command(command)
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        "gateway", "zone", "temperatureControl", 21, path=None
    )


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
