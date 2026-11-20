"""Tests for Daikin Onecta refresh button entities."""

import asyncio
from unittest.mock import AsyncMock

from daikin_onecta.exceptions import OnectaConnectionError, OnectaRateLimitError
from daikin_onecta.models import GatewayDevice
from daikin_onecta.rate_limit import RateLimit
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import MockOnectaClient
from .platform_helpers import _async_fire_coordinator_update
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices

ACCOUNT_REFRESH_BUTTON_ENTITY_ID = "button.daikin_onecta_account_refresh"


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
        {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
        blocking=True,
    )

    coordinator.async_manual_refresh.assert_awaited_once()


async def test_refresh_button_reuses_in_flight_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reuse a scheduled poll even if a write starts cooldown meanwhile."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.reset_mock()
    request_started = asyncio.Event()
    finish_request = asyncio.Event()

    async def delayed_get_gateway_devices() -> list[GatewayDevice]:
        request_started.set()
        await finish_request.wait()
        return _load_gateway_devices("dry")

    mock_onecta_client.get_gateway_devices.side_effect = delayed_get_gateway_devices
    assert coordinator.update_interval is not None
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await request_started.wait()

    button_task = hass.async_create_task(
        hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
            blocking=True,
        )
    )
    await asyncio.sleep(0)
    coordinator._last_patch_call = dt_util.utcnow()
    finish_request.set()
    await button_task
    await hass.async_block_till_done()

    mock_onecta_client.get_gateway_devices.assert_awaited_once_with()
    assert coordinator.last_update_success


async def test_refresh_button_reports_failed_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A failed cloud refresh is reported to the service caller."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data

    coordinator.async_manual_refresh = AsyncMock(return_value=False)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "refresh_failed"
    assert err.value.translation_placeholders is None
    coordinator.async_manual_refresh.assert_awaited_once()


async def test_refresh_button_respects_polling_backoff(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Button presses are deferred while Daikin's Retry-After is active."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.side_effect = OnectaRateLimitError(
        RateLimit(retry_after=300), method="GET", path="/v1/gateway-devices"
    )
    assert coordinator.update_interval is not None
    freezer.tick(coordinator.update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_onecta_client.get_gateway_devices.assert_awaited_once_with()
    mock_onecta_client.get_gateway_devices.reset_mock()
    mock_onecta_client.get_gateway_devices.side_effect = None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_key == "manual_refresh_deferred"
    assert err.value.translation_placeholders == {"seconds": "300"}
    mock_onecta_client.get_gateway_devices.assert_not_awaited()


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
            {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "manual_refresh_deferred"
    assert err.value.translation_placeholders == {"seconds": "60"}
    assert coordinator.last_update_success
    mock_onecta_client.get_gateway_devices.assert_awaited_once()


async def test_refresh_button_reports_post_write_cooldown(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not silently report success when refresh is deferred after a write."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
        "network unavailable", method="GET", path="/v1/gateway-devices"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert not coordinator.last_update_success
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
    state = hass.states.get(entity_id)
    assert state is not None and state.state == "unavailable"

    mock_onecta_client.get_gateway_devices.reset_mock()
    mock_onecta_client.get_gateway_devices.side_effect = None
    command = AsyncMock()
    assert await coordinator.async_execute_command(lambda _client: command())
    mock_onecta_client.get_gateway_devices.reset_mock()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "manual_refresh_deferred"
    assert err.value.translation_placeholders == {"seconds": "30"}
    mock_onecta_client.get_gateway_devices.assert_not_awaited()
    assert not coordinator.last_update_success
    assert hass.states.get(state.entity_id) == state


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
    state = hass.states.get(ACCOUNT_REFRESH_BUTTON_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"

    mock_onecta_client.get_gateway_devices.side_effect = None
    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices("dry")
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: ACCOUNT_REFRESH_BUTTON_ENTITY_ID},
        blocking=True,
    )

    assert coordinator.last_update_success
    mock_onecta_client.get_gateway_devices.assert_awaited()
