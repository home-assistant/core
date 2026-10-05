"""Tests for the Daikin Onecta API client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta import OnectaApiError, OnectaConnectionError, OnectaRateLimitError
from daikin_onecta.rate_limit import RateLimit
import pytest

from homeassistant.components.daikin_onecta.daikin_api import DaikinApi
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_get_device_details_propagates_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Propagate library connection errors to the coordinator."""
    with patch(
        "homeassistant.components.daikin_onecta.daikin_api.OnectaClient.get_gateway_devices",
        new=AsyncMock(
            side_effect=OnectaConnectionError(
                "network unavailable",
                method="GET",
                path="/v1/gateway-devices",
            )
        ),
    ):
        api = DaikinApi(hass, config_entry, MagicMock())
        with pytest.raises(OnectaConnectionError, match="network unavailable"):
            await api.get_cloud_device_details()


async def test_access_token(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Return the OAuth access token after ensuring it is valid."""
    api = DaikinApi(hass, config_entry, MagicMock())
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
    api = DaikinApi(hass, config_entry, MagicMock())
    api.client.get_gateway_devices = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60),
            method="GET",
            path="/v1/gateway-devices",
        )
    )

    with pytest.raises(OnectaRateLimitError):
        await api.get_cloud_device_details()


async def test_get_device_details_respects_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Do not fetch cloud data while a successful write is in its cooldown."""
    api = DaikinApi(hass, config_entry, MagicMock())
    api._last_patch_call = dt_util.utcnow()
    api.client.get_gateway_devices = AsyncMock()

    assert await api.get_cloud_device_details(cooldown=timedelta(seconds=30)) is None
    api.client.get_gateway_devices.assert_not_awaited()


@patch("homeassistant.components.daikin_onecta.daikin_api.dt_util.utcnow")
async def test_get_device_details_uses_utc_across_dst_rollback(
    mock_utcnow: MagicMock,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """End cooldown based on elapsed time, not the local DST clock."""
    api = DaikinApi(hass, config_entry, MagicMock())
    # In Amsterdam, local time moves from 02:59 CEST back to 02:01 CET here.
    api._last_patch_call = datetime(2026, 10, 25, 0, 59, tzinfo=UTC)
    mock_utcnow.return_value = datetime(2026, 10, 25, 1, 1, tzinfo=UTC)
    api.client.get_gateway_devices = AsyncMock(return_value=[])

    assert await api.get_cloud_device_details(cooldown=timedelta(seconds=30)) == []
    api.client.get_gateway_devices.assert_awaited_once_with()


async def test_write_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Record successful writes."""
    api = DaikinApi(hass, config_entry, MagicMock())
    command = AsyncMock()

    assert await api.async_execute_command(command)
    command.assert_awaited_once_with(api.client)
    assert api.last_patch_call is not None


async def test_write_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for API write failures."""
    api = DaikinApi(hass, config_entry, MagicMock())
    command = AsyncMock(
        side_effect=OnectaApiError(
            500, "failed", method="PATCH", path="/v1/management-points/point"
        )
    )

    assert not await api.async_execute_command(command)
    assert api.last_patch_call is None
    assert (
        "Daikin request PATCH /v1/management-points/point failed with HTTP 500"
        in caplog.text
    )


async def test_write_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false for rate-limited writes."""
    api = DaikinApi(hass, config_entry, MagicMock())
    command = AsyncMock(
        side_effect=OnectaRateLimitError(
            RateLimit(retry_after=60),
            method="PATCH",
            path="/v1/management-points/point",
        )
    )

    assert not await api.async_execute_command(command)
    assert api.last_patch_call is None
    assert (
        "Daikin request PATCH /v1/management-points/point was rate limited; "
        "retry after 60 seconds" in caplog.text
    )


async def test_write_timeout(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Return false when refreshing the OAuth token times out during a write."""
    api = DaikinApi(hass, config_entry, MagicMock())
    command = AsyncMock(side_effect=TimeoutError)

    assert not await api.async_execute_command(command)
    assert api.last_patch_call is None
    assert "Daikin request timed out" in caplog.text


async def test_rate_limits_preserve_unknown_values(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep rate-limit values unavailable when Daikin did not send them."""
    api = DaikinApi(hass, config_entry, MagicMock())
    api.client.rate_limit = RateLimit()

    assert api.rate_limits == {
        "minute": None,
        "day": None,
        "remaining_minutes": None,
        "remaining_day": None,
        "retry_after": None,
        "ratelimit_reset": None,
    }
