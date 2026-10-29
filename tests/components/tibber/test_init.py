"""Test loading of the Tibber config entry."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import time
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
import tibber

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber import DOMAIN
from homeassistant.components.tibber.const import AUTH_IMPLEMENTATION
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import create_tibber_device, create_tibber_home

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("recorder_mock", "setup_credentials")
@pytest.mark.parametrize(
    ("method", "error"),
    [
        pytest.param(
            "fetch_consumption_data_active_homes",
            tibber.RetryableHttpExceptionError(
                200, "Consumption failed", "INTERNAL_SERVER_ERROR"
            ),
            id="consumption",
        ),
        pytest.param(
            "fetch_production_data_active_homes",
            tibber.RetryableHttpExceptionError(
                200, "Production failed", "INTERNAL_SERVER_ERROR"
            ),
            id="production",
        ),
        pytest.param(
            "fetch_consumption_data_active_homes", TimeoutError(), id="timeout"
        ),
        pytest.param(
            "fetch_consumption_data_active_homes",
            aiohttp.ClientError(),
            id="client_error",
        ),
    ],
)
async def test_setup_history_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    method: str,
    error: Exception,
) -> None:
    """History failures allow setup, recover on schedule, and stop on unload."""
    home = create_tibber_home()
    home.has_real_time_consumption = True
    home.rt_subscribe = AsyncMock()
    tibber_mock.get_homes.return_value = [home]
    device = create_tibber_device(state_of_charge=72.0)
    tibber_mock.data_api.get_all_devices.return_value = {device.id: device}
    tibber_mock.data_api.update_devices.return_value = {device.id: device}
    history_fetch = getattr(tibber_mock, method)
    history_fetch.side_effect = error

    await hass.async_start()
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    coordinator = config_entry.runtime_data.data_coordinator
    assert coordinator is not None
    assert not coordinator.last_update_success
    price_id = entity_registry.async_get_entity_id("sensor", DOMAIN, home.home_id)
    battery_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "device-id_storage.stateOfCharge"
    )
    history_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "home-id_month_cost"
    )
    assert hass.states.get(price_id).state == "1.25"
    assert hass.states.get(battery_id).state == "72.0"
    assert hass.states.get(history_id).state == STATE_UNAVAILABLE
    home.rt_subscribe.assert_awaited_once()
    assert "will retry" in caplog.text
    caplog.clear()

    freezer.tick(timedelta(minutes=21))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert history_fetch.await_count == 2
    assert hass.states.get(history_id).state == STATE_UNAVAILABLE
    assert "will retry" not in caplog.text

    history_fetch.side_effect = None
    freezer.tick(timedelta(minutes=21))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert history_fetch.await_count == 3
    assert coordinator.last_update_success
    assert hass.states.get(history_id).state == "111.1"
    assert config_entry.state is ConfigEntryState.LOADED
    home.rt_subscribe.assert_awaited_once()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    freezer.tick(timedelta(minutes=21))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert history_fetch.await_count == 3
    tibber_mock.rt_disconnect.assert_awaited_once()


async def test_entry_unload(
    recorder_mock: Recorder, hass: HomeAssistant, mock_tibber_setup: MagicMock
) -> None:
    """Test unloading the entry."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "tibber")
    assert entry.state is ConfigEntryState.LOADED

    mock_tibber_setup.set_access_token.reset_mock()
    await hass.config_entries.async_unload(entry.entry_id)
    mock_tibber_setup.rt_disconnect.assert_called_once()
    mock_tibber_setup.set_access_token.assert_not_called()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def _hang_forever() -> None:
    """Simulate a realtime disconnect that never completes."""
    await asyncio.Event().wait()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(_hang_forever, id="timeout"),
        pytest.param(Exception("Disconnect failed"), id="exception"),
    ],
)
async def test_entry_unload_rt_disconnect_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_tibber_setup: MagicMock,
    side_effect: Exception | Callable[[], Awaitable[None]],
) -> None:
    """Test the entry unloads even if disconnecting the client fails."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "tibber")
    assert entry.state is ConfigEntryState.LOADED

    mock_tibber_setup.rt_disconnect.side_effect = side_effect
    with patch("homeassistant.components.tibber.DISCONNECT_TIMEOUT", 0.05):
        await hass.config_entries.async_unload(entry.entry_id)
    mock_tibber_setup.rt_disconnect.assert_called_once()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def _async_trigger_client_fetch(hass: HomeAssistant) -> None:
    """Make the integration fetch its client through a public entity action."""
    await hass.services.async_call(
        "notify",
        "send_message",
        {"entity_id": "notify.tibber", "message": "message"},
        blocking=True,
    )


@pytest.mark.usefixtures("recorder_mock", "mock_tibber_setup")
async def test_client_created_once_and_reused(
    hass: HomeAssistant,
    tibber_client_cls: MagicMock,
) -> None:
    """Ensure setup builds one authenticated client that later fetches reuse."""
    tibber_client_cls.assert_called_once_with(
        access_token="test-token",
        websession=ANY,
        time_zone=ANY,
        ssl=ANY,
        refresh_access_token=ANY,
    )

    # The library refreshes its own realtime token through this callback.
    refresh_access_token = tibber_client_cls.call_args.kwargs["refresh_access_token"]
    assert await refresh_access_token() == "test-token"

    await _async_trigger_client_fetch(hass)

    tibber_client_cls.assert_called_once()


@pytest.mark.usefixtures("recorder_mock", "mock_tibber_setup")
async def test_rotated_token_returned_by_refresh_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_client_cls: MagicMock,
) -> None:
    """Ensure the refresh callback returns a rotated OAuth token."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            "token": {**config_entry.data["token"], CONF_ACCESS_TOKEN: "token-2"},
        },
    )

    await _async_trigger_client_fetch(hass)

    tibber_client_cls.assert_called_once()
    refresh_access_token = tibber_client_cls.call_args.kwargs["refresh_access_token"]
    assert await refresh_access_token() == "token-2"


@pytest.mark.usefixtures("recorder_mock", "tibber_mock", "setup_credentials")
async def test_setup_missing_access_token_triggers_reauth(
    hass: HomeAssistant,
) -> None:
    """Ensure an OAuth token without an access token triggers reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            AUTH_IMPLEMENTATION: DOMAIN,
            "token": {
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_at": time.time() + 3600,
            },
        },
        unique_id="tibber",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_requires_data_api_reauth(hass: HomeAssistant) -> None:
    """Ensure legacy entries trigger reauth to configure Data API."""
    hass.config.components.add("recorder")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "legacy-token"},
        unique_id="legacy",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
