"""Tests for the Daikin Onecta coordinator client adapter."""

from datetime import UTC, datetime, timedelta

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

from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
)

from .conftest import FAKE_ACCESS_TOKEN, MockOnectaClient
from .platform_helpers import _async_fire_coordinator_update, _async_setup_fixture


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> OnectaDataUpdateCoordinator:
    """Set up the coordinator through its config entry."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    return config_entry.runtime_data


async def test_scheduled_poll_marks_connection_error_unsuccessful(
    coordinator: OnectaDataUpdateCoordinator,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Mark a scheduled poll unsuccessful after a library connection error."""
    mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
        "network unavailable", method="GET", path="/v1/gateway-devices"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert not coordinator.last_update_success


async def test_access_token(coordinator: OnectaDataUpdateCoordinator) -> None:
    """Return the OAuth access token after ensuring it is valid."""
    assert await coordinator.async_get_access_token() == FAKE_ACCESS_TOKEN


async def test_scheduled_poll_sets_rate_limit_backoff(
    coordinator: OnectaDataUpdateCoordinator,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Apply the rate-limit deadline after a scheduled poll gets a 429."""
    mock_onecta_client.get_gateway_devices.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert coordinator.last_update_success
    assert coordinator.update_interval == timedelta(seconds=60)


async def test_get_sites(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Fetch sites without using the normal polling endpoint."""
    sites = [Site(id="site-1", gateway_device_ids=["gateway-1"])]
    mock_onecta_client.get_sites.return_value = sites

    assert await coordinator.async_get_sites() == sites
    mock_onecta_client.get_sites.assert_awaited_once_with()


async def test_get_sites_rate_limit_sets_shared_backoff(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A Sites rate limit prevents later explicit cloud requests until retry."""
    mock_onecta_client.get_sites.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=60), method="GET", path="/v1/sites"
    )
    with pytest.raises(OnectaRateLimitError):
        await coordinator.async_get_sites()

    with pytest.raises(OnectaRateLimitError):
        await coordinator.async_get_sites()
    mock_onecta_client.get_sites.assert_awaited_once_with()


async def test_scheduled_poll_respects_write_cooldown(
    hass: HomeAssistant,
    coordinator: OnectaDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep scheduled polling within the write cooldown out of the cloud."""
    mock_onecta_client.get_gateway_devices.reset_mock()
    freezer.tick(coordinator.update_interval - timedelta(seconds=1))
    assert await coordinator.async_execute_command(
        lambda client: client.patch_characteristic("gateway", "point", "power", "on")
    )
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_onecta_client.get_gateway_devices.assert_not_awaited()


async def test_get_device_details_uses_elapsed_utc_time(
    hass: HomeAssistant,
    coordinator: OnectaDataUpdateCoordinator,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Fetch after the post-write cooldown expires across a DST transition."""
    freezer.move_to(datetime(2026, 10, 25, 0, 59, tzinfo=UTC))
    mock_onecta_client.get_gateway_devices.reset_mock()
    coordinator.schedule_post_write_refresh()
    assert await coordinator.async_execute_command(
        lambda client: client.patch_characteristic("gateway", "point", "power", "on")
    )
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_onecta_client.get_gateway_devices.assert_awaited_once_with()


async def test_write_success(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Record successful writes."""
    assert await coordinator.async_execute_command(
        lambda client: client.patch_characteristic("gateway", "point", "power", "on")
    )
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        "gateway", "point", "power", "on", path=None
    )


async def test_write_preserves_oauth_token_rejection(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Propagate token-provider OAuth failures from the pinned client unchanged."""
    token_url = URL("https://idp.onecta.daikineurope.com/v1/oidc/token")
    token_error = OAuth2TokenRequestReauthError(
        domain=coordinator.config_entry.domain,
        request_info=RequestInfo(
            url=token_url, method="POST", headers={}, real_url=token_url
        ),
        status=401,
        message="invalid_grant",
    )
    mock_onecta_client.patch_characteristic.side_effect = token_error

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "zone", "temperatureControl", 21)

    assert not await coordinator.async_execute_command(command)
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        "gateway", "zone", "temperatureControl", 21, path=None
    )


async def test_write_api_error(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for API write failures."""
    mock_onecta_client.patch_characteristic.side_effect = OnectaApiError(
        500, "failed", method="PATCH", path="/v1/management-points/point"
    )

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "point", "power", "on")

    assert not await coordinator.async_execute_command(command)
    assert (
        "Daikin request PATCH /v1/management-points/point failed with HTTP 500"
        in caplog.text
    )


async def test_write_connection_error(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for connection failures without recording a successful write."""
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "network unavailable",
        method="PATCH",
        path="/v1/management-points/point",
    )

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "point", "power", "on")

    assert not await coordinator.async_execute_command(command)
    assert (
        "Daikin request PATCH /v1/management-points/point failed to connect: "
        "network unavailable" in caplog.text
    )


async def test_write_rate_limit(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for rate-limited writes."""
    mock_onecta_client.patch_characteristic.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=60),
        method="PATCH",
        path="/v1/management-points/point",
    )

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "point", "power", "on")

    assert not await coordinator.async_execute_command(command)
    assert (
        "Daikin request PATCH /v1/management-points/point was rate limited; "
        "retry after 60 seconds" in caplog.text
    )


async def test_write_token_connection_error(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false when refreshing the OAuth token fails during a write."""
    mock_onecta_client.patch_characteristic.side_effect = (
        OAuth2TokenRequestConnectionError(domain=coordinator.config_entry.domain)
    )

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "point", "power", "on")

    assert not await coordinator.async_execute_command(command)
    assert "OAuth2TokenRequestConnectionError" in caplog.text


async def test_write_timeout(
    coordinator: OnectaDataUpdateCoordinator,
    mock_onecta_client: MockOnectaClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false when a token refresh times out during a write."""
    mock_onecta_client.patch_characteristic.side_effect = TimeoutError

    async def command(client: OnectaClient) -> None:
        await client.patch_characteristic("gateway", "point", "power", "on")

    assert not await coordinator.async_execute_command(command)
    assert "Daikin request timed out" in caplog.text


async def test_unknown_rate_limit_uses_default_polling_budget(
    coordinator: OnectaDataUpdateCoordinator,
) -> None:
    """Use the conservative polling budget when response headers are absent."""
    coordinator.client.rate_limit = RateLimit()
    assert coordinator._polling_intervals() == (
        timedelta(seconds=594),
        timedelta(seconds=1782),
    )


async def test_rate_limits_preserve_unknown_values(
    coordinator: OnectaDataUpdateCoordinator,
) -> None:
    """Keep rate-limit values unavailable when Daikin did not send them."""
    coordinator.client.rate_limit = RateLimit()

    assert coordinator.rate_limits == {
        "minute": None,
        "day": None,
        "remaining_minutes": None,
        "remaining_day": None,
        "retry_after": None,
        "ratelimit_reset": None,
    }
