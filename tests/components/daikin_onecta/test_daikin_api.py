"""Tests for the Daikin Onecta API client."""

from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta import OnectaApiError, OnectaConnectionError, OnectaRateLimitError
from daikin_onecta.rate_limit import RateLimit
import pytest

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.daikin_api import DaikinApi
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

EXPECTED_RATE_LIMIT_ISSUES = 2


async def test_get_device_details_propagates_connection_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Propagate library connection errors to the coordinator."""
    with patch(
        "homeassistant.components.daikin_onecta.daikin_api.OnectaClient.get_gateway_devices",
        new=AsyncMock(side_effect=OnectaConnectionError("network unavailable")),
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
    """Create rate-limit issues and propagate a library rate-limit error."""
    api = DaikinApi(hass, config_entry, MagicMock())
    api.create_rate_limit_issues = MagicMock()
    api.client.get_gateway_devices = AsyncMock(side_effect=OnectaRateLimitError(60))

    with pytest.raises(OnectaRateLimitError):
        await api.get_cloud_device_details()

    api.create_rate_limit_issues.assert_called_once()


async def test_get_device_details_updates_rate_limit_issues(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Clear stale rate-limit issues after a successful device request."""
    api = DaikinApi(hass, config_entry, MagicMock())
    api.client.get_gateway_devices = AsyncMock(return_value=[])
    api.update_rate_limit_issues = MagicMock()

    assert await api.get_cloud_device_details() == []
    api.update_rate_limit_issues.assert_called_once()


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("patch_characteristic", ("gateway", "point", "onOffMode", "on")),
        (
            "post_management_point",
            ("gateway", "point", "holiday-mode", {"enabled": False}),
        ),
        (
            "put_management_point",
            ("gateway", "point", "schedule/heating/current", {"enabled": False}),
        ),
    ],
)
async def test_write_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    method: str,
    arguments: tuple,
) -> None:
    """Record successful writes and refresh rate-limit issues."""
    api = DaikinApi(hass, config_entry, MagicMock())
    setattr(api.client, method, AsyncMock())
    api.update_rate_limit_issues = MagicMock()

    assert await getattr(api, method)(*arguments)
    getattr(api.client, method).assert_awaited_once()
    assert api.last_patch_call is not None
    api.update_rate_limit_issues.assert_called_once()


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("patch_characteristic", ("gateway", "point", "onOffMode", "on")),
        (
            "post_management_point",
            ("gateway", "point", "holiday-mode", {"enabled": False}),
        ),
        (
            "put_management_point",
            ("gateway", "point", "schedule/heating/current", {"enabled": False}),
        ),
    ],
)
async def test_write_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    method: str,
    arguments: tuple,
) -> None:
    """Return false for API write failures."""
    api = DaikinApi(hass, config_entry, MagicMock())
    setattr(api.client, method, AsyncMock(side_effect=OnectaApiError(500, "failed")))

    assert not await getattr(api, method)(*arguments)
    assert api.last_patch_call is None


@pytest.mark.parametrize(
    ("method", "arguments"),
    [
        ("patch_characteristic", ("gateway", "point", "onOffMode", "on")),
        (
            "post_management_point",
            ("gateway", "point", "holiday-mode", {"enabled": False}),
        ),
        (
            "put_management_point",
            ("gateway", "point", "schedule/heating/current", {"enabled": False}),
        ),
    ],
)
async def test_write_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    method: str,
    arguments: tuple,
) -> None:
    """Create a repair issue and return false for rate-limited writes."""
    api = DaikinApi(hass, config_entry, MagicMock())
    setattr(api.client, method, AsyncMock(side_effect=OnectaRateLimitError(60)))
    api.create_rate_limit_issues = MagicMock()

    assert not await getattr(api, method)(*arguments)
    api.create_rate_limit_issues.assert_called_once()
    assert api.last_patch_call is None


async def test_rate_limit_issue_updates(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Create and remove Home Assistant rate-limit repair issues."""
    api = DaikinApi(hass, config_entry, MagicMock())
    api.client.rate_limit = RateLimit(minute_remaining=0, day_remaining=0)

    with patch(
        "homeassistant.components.daikin_onecta.daikin_api.ir.async_create_issue"
    ) as create_issue:
        api.create_rate_limit_issues()

    assert create_issue.call_count == EXPECTED_RATE_LIMIT_ISSUES

    api.client.rate_limit = RateLimit(minute_remaining=1, day_remaining=1)
    with patch(
        "homeassistant.components.daikin_onecta.daikin_api.ir.async_delete_issue"
    ) as delete_issue:
        api.update_rate_limit_issues()

    delete_issue.assert_any_call(hass, DOMAIN, "minute_rate_limit")
    delete_issue.assert_any_call(hass, DOMAIN, "day_rate_limit")


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

    with patch(
        "homeassistant.components.daikin_onecta.daikin_api.ir.async_create_issue"
    ) as create_issue:
        api.create_rate_limit_issues()

    create_issue.assert_not_called()
