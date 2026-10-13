"""Tests for Daikin Onecta system health."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.system_health import (
    async_register,
    system_health_info,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_system_health_register() -> None:
    """Register the system health callback."""
    register = MagicMock()

    async_register(MagicMock(), register)

    register.async_register_info.assert_called_once_with(system_health_info)


async def test_system_health_ignores_unloaded_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Ignore entries that do not have running integration data."""
    config_entry.add_to_hass(hass)

    assert await system_health_info(hass) == {}


async def test_system_health_info(hass: HomeAssistant) -> None:
    """Report rate limit and token information for a loaded entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        state=ConfigEntryState.LOADED,
    )
    config_entry.runtime_data = MagicMock(
        rate_limits={
            "minute": 10,
            "day": 200,
            "remaining_minutes": 9,
            "remaining_day": 199,
            "retry_after": None,
            "ratelimit_reset": None,
        },
        session=MagicMock(valid_token=True),
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.daikin_onecta.system_health."
        "system_health.async_check_can_reach_url",
        new=AsyncMock(return_value="ok"),
    ):
        info = await system_health_info(hass)

    assert info["max_minute"] == 10
    assert info["max_day"] == 200
    assert info["remaining_minute"] == 9
    assert info["remaining_day"] == 199
    assert info["oauth2_token_valid"] is True
    assert await info["api_status"] == "ok"
    assert await info["oauth2_status"] == "ok"


async def test_system_health_reports_every_loaded_account(
    hass: HomeAssistant,
) -> None:
    """Include cached health data for every configured Daikin account."""
    for title, unique_id, remaining in (
        ("Account one", "account-1", 199),
        ("Account two", "account-2", 399),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title=title,
            unique_id=unique_id,
            state=ConfigEntryState.LOADED,
        )
        config_entry.runtime_data = MagicMock(
            rate_limits={
                "minute": 10,
                "day": remaining + 1,
                "remaining_minutes": 9,
                "remaining_day": remaining,
                "retry_after": None,
                "ratelimit_reset": None,
            },
            session=MagicMock(valid_token=True),
        )
        config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.daikin_onecta.system_health."
        "system_health.async_check_can_reach_url",
        new=AsyncMock(return_value="ok"),
    ):
        info = await system_health_info(hass)

    assert "Account one" in info["remaining_day"]
    assert "199" in info["remaining_day"]
    assert "Account two" in info["remaining_day"]
    assert "399" in info["remaining_day"]
    assert await info["api_status"] == "ok"
    assert await info["oauth2_status"] == "ok"
