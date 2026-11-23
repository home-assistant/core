"""Tests for Daikin Onecta system health."""

from unittest.mock import MagicMock, PropertyMock, patch

from daikin_onecta.client import ONECTA_API_URL
from daikin_onecta.rate_limit import RateLimit
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.syrupy import HomeAssistantSnapshotExtension
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.daikin_onecta.const import DOMAIN, OAUTH2_AUTHORIZE
from homeassistant.components.daikin_onecta.system_health import (
    async_register,
    system_health_info,
)
from homeassistant.core import HomeAssistant

from .platform_helpers import _async_setup_fixture, _load_gateway_devices


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


async def test_system_health_info(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    snapshot: SnapshotAssertion,
) -> None:
    """Report rate limit and token information for a loaded entry."""
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    config_entry.runtime_data.client.rate_limit = RateLimit(
        minute_limit=10, day_limit=200, minute_remaining=9, day_remaining=199
    )

    aioclient_mock.get(ONECTA_API_URL, status=503)
    aioclient_mock.get(OAUTH2_AUTHORIZE, status=200)
    coordinator = config_entry.runtime_data
    cached_rate_limits = coordinator.rate_limits
    with patch.object(
        type(coordinator),
        "rate_limits",
        new_callable=PropertyMock,
        return_value=cached_rate_limits,
    ) as rate_limits:
        info = await system_health_info(hass)
        assert rate_limits.call_count == 1

    info["api_status"] = await info["api_status"]
    info["oauth2_status"] = await info["oauth2_status"]

    assert info == snapshot(extension_class=HomeAssistantSnapshotExtension)


async def test_system_health_reports_every_loaded_account(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Include cached health data for every configured Daikin account."""
    hass.config_entries.async_update_entry(config_entry, unique_id="account-1")
    await _async_setup_fixture(hass, config_entry, "minimal_data")
    first_coordinator = config_entry.runtime_data
    first_coordinator.client.rate_limit = RateLimit(
        minute_limit=10, day_limit=200, minute_remaining=9, day_remaining=199
    )

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Account two",
        unique_id="account-2",
        data=config_entry.data,
    )
    second_entry.add_to_hass(hass)
    second_devices = _load_gateway_devices("minimal_data")
    second_devices[0].id = "second-gateway"
    await _async_setup_fixture(
        hass, second_entry, "minimal_data", gateway_devices=second_devices
    )
    second_coordinator = second_entry.runtime_data
    second_coordinator.client.rate_limit = RateLimit(
        minute_limit=10, day_limit=400, minute_remaining=9, day_remaining=399
    )
    entry_ids = [config_entry.entry_id, second_entry.entry_id]

    aioclient_mock.get(ONECTA_API_URL, status=503)
    aioclient_mock.get(OAUTH2_AUTHORIZE, status=200)
    info = await system_health_info(hass)

    assert entry_ids[0] in info["remaining_day"]
    assert "199" in info["remaining_day"]
    assert entry_ids[1] in info["remaining_day"]
    assert "399" in info["remaining_day"]
    assert "Account one" not in info["remaining_day"]
    assert "Account two" not in info["remaining_day"]
    assert await info["api_status"] == "ok"
    assert await info["oauth2_status"] == "ok"
