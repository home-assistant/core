"""Tests for Daikin Onecta system health."""

from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta.client import ONECTA_API_URL
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.system_health import (
    _entry_info,
    async_register,
    system_health_info,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


def test_system_health_register() -> None:
    """Register the system health callback."""
    register = MagicMock()

    async_register(MagicMock(), register)

    register.async_register_info.assert_called_once_with(system_health_info)


def test_system_health_reads_rate_limits_once() -> None:
    """Build all health fields from one cached rate-limit snapshot."""

    class RuntimeData:
        rate_limit_reads = 0
        session = MagicMock(valid_token=True)

        @property
        def rate_limits(self) -> dict[str, int | None]:
            self.rate_limit_reads += 1
            return {
                "minute": 10,
                "day": 200,
                "remaining_minutes": 9,
                "remaining_day": 199,
                "retry_after": None,
                "ratelimit_reset": None,
            }

    config_entry = MockConfigEntry(domain=DOMAIN)
    runtime_data = RuntimeData()
    config_entry.runtime_data = runtime_data

    info = _entry_info(config_entry)

    assert info["max_minute"] == 10
    assert info["remaining_day"] == 199
    assert runtime_data.rate_limit_reads == 1


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
    ) as check_url:
        info = await system_health_info(hass)

    assert info["max_minute"] == 10
    assert info["max_day"] == 200
    assert info["remaining_minute"] == 9
    assert info["remaining_day"] == 199
    assert info["oauth2_token_valid"] is True
    assert await info["api_status"] == "ok"
    assert await info["oauth2_status"] == "ok"
    assert check_url.await_args_list[0].args[1] == ONECTA_API_URL


async def test_system_health_reports_every_loaded_account(
    hass: HomeAssistant,
) -> None:
    """Include cached health data for every configured Daikin account."""
    entry_ids: list[str] = []
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
        entry_ids.append(config_entry.entry_id)

    with patch(
        "homeassistant.components.daikin_onecta.system_health."
        "system_health.async_check_can_reach_url",
        new=AsyncMock(return_value="ok"),
    ):
        info = await system_health_info(hass)

    assert entry_ids[0] in info["remaining_day"]
    assert "199" in info["remaining_day"]
    assert entry_ids[1] in info["remaining_day"]
    assert "399" in info["remaining_day"]
    assert "Account one" not in info["remaining_day"]
    assert "Account two" not in info["remaining_day"]
    assert await info["api_status"] == "ok"
    assert await info["oauth2_status"] == "ok"
