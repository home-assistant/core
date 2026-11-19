"""Tests for Daikin Onecta refresh button entities."""

from datetime import timedelta
from unittest.mock import AsyncMock

from daikin_onecta.exceptions import OnectaConnectionError, OnectaRateLimitError
from daikin_onecta.rate_limit import RateLimit
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import MockOnectaClient
from .platform_helpers import _async_fire_coordinator_update
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


async def test_refresh_button_requests_coordinator_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The refresh button requests one coordinator refresh."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    coordinator.async_manual_refresh = AsyncMock()
    coordinator.async_manual_refresh.return_value = True

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
        blocking=True,
    )

    coordinator.async_manual_refresh.assert_awaited_once()


async def test_refresh_button_reports_failed_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A failed cloud refresh is reported to the service caller."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data

    async def fail_refresh() -> None:
        coordinator.last_update_success = False

    coordinator.async_manual_refresh = AsyncMock(side_effect=fail_refresh)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "refresh_failed"
    assert err.value.translation_placeholders is None
    coordinator.async_manual_refresh.assert_awaited_once()


@pytest.mark.parametrize("last_update_success", [True, False])
async def test_refresh_button_bypasses_polling_backoff(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
    last_update_success: bool,
) -> None:
    """Manual button refreshes reach the cloud during scheduled poll backoff."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    coordinator._polling_backoff_until = dt_util.utcnow() + timedelta(minutes=5)
    coordinator.last_update_success = last_update_success
    mock_onecta_client.get_gateway_devices.reset_mock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
        blocking=True,
    )

    mock_onecta_client.get_gateway_devices.assert_awaited_once()
    assert coordinator.last_update_success


async def test_refresh_button_reports_rate_limited_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A 429 during manual refresh is reported even when cached data is good."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.reset_mock()
    mock_onecta_client.get_gateway_devices.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=60), method="GET", path="/v1/gateway-devices"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "refresh_failed"
    assert coordinator.last_update_success
    mock_onecta_client.get_gateway_devices.assert_awaited_once()


async def test_refresh_button_reports_post_write_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not silently report success when refresh is deferred after a write."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    coordinator._last_patch_call = dt_util.utcnow()
    mock_onecta_client.get_gateway_devices.reset_mock()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "manual_refresh_deferred"
    assert err.value.translation_placeholders == {"seconds": "30"}
    mock_onecta_client.get_gateway_devices.assert_not_awaited()


async def test_refresh_button_recovers_after_failed_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep the button usable to retry a failed poll without reloading."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
        "network unavailable", method="GET", path="/v1/gateway-devices"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert not coordinator.last_update_success
    state = hass.states.get("button.daikin_onecta_account_refresh")
    assert state is not None
    assert state.state != "unavailable"

    mock_onecta_client.get_gateway_devices.side_effect = None
    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices("dry")
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
        blocking=True,
    )

    assert coordinator.last_update_success
    mock_onecta_client.get_gateway_devices.assert_awaited()
