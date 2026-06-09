"""Test init for Anova."""

from unittest.mock import AsyncMock, patch

from anova_wifi import AnovaApi, WebsocketFailure

from homeassistant.components.anova.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import async_init_integration, create_entry
from .conftest import MockedAnovaWebsocketHandler

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass)
    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state == "idle"


async def test_wrong_login(
    hass: HomeAssistant, anova_api_wrong_login: AnovaApi
) -> None:
    """Test for setup failure if connection to Anova is missing."""
    entry = create_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, anova_api: AnovaApi) -> None:
    """Test successful unload of entry."""
    entry = await async_init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_no_devices_found(
    hass: HomeAssistant,
    anova_api_no_devices: AnovaApi,
) -> None:
    """Test when there don't seem to be any devices on the account."""
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_websocket_failure(
    hass: HomeAssistant,
    anova_api_websocket_failure: AnovaApi,
) -> None:
    """Test that we successfully handle a websocket failure on setup."""
    entry = await async_init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_websocket_reconnects_on_disconnect(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test that the integration automatically reconnects when the websocket drops."""
    entry = await async_init_integration(hass)

    initial_call_count = entry.runtime_data.api.create_websocket.call_count
    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    ws_handler.simulate_disconnect()
    # First call lets _wait_for_disconnect complete and schedules the done callback.
    # Second call processes the done callback, creates the reconnect task, and waits for it.
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.runtime_data.api.create_websocket.call_count == initial_call_count + 1
    new_ws_handler = entry.runtime_data.api.websocket_handler
    assert new_ws_handler is not ws_handler
    for coordinator in entry.runtime_data.coordinators:
        device = new_ws_handler.devices.get(coordinator.device_unique_id)
        assert device is not None
        assert device.update_listener == coordinator.async_set_updated_data


async def test_websocket_reconnects_after_auth_expiry(
    hass: HomeAssistant,
    anova_api: AnovaApi,
) -> None:
    """Test that the integration re-authenticates and reconnects when auth has expired."""
    entry = await async_init_integration(hass)

    ws_handler = entry.runtime_data.api.websocket_handler
    assert isinstance(ws_handler, MockedAnovaWebsocketHandler)

    # Simulate: first create_websocket call fails (stale JWT), then succeeds after re-auth.
    original_side_effect = entry.runtime_data.api.create_websocket.side_effect
    call_count = 0

    async def create_websocket_after_reauth():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise WebsocketFailure("Token expired")
        await original_side_effect()

    entry.runtime_data.api.create_websocket.side_effect = create_websocket_after_reauth
    entry.runtime_data.api.authenticate = AsyncMock()

    ws_handler.simulate_disconnect()
    await hass.async_block_till_done()
    await hass.async_block_till_done(wait_background_tasks=True)

    entry.runtime_data.api.authenticate.assert_called_once()
    assert call_count == 2
    new_ws_handler = entry.runtime_data.api.websocket_handler
    assert new_ws_handler is not ws_handler


async def test_migration_removing_devices_in_config_entry(
    hass: HomeAssistant, anova_api: AnovaApi
) -> None:
    """Test a successful setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Anova",
        data={
            CONF_USERNAME: "sample@gmail.com",
            CONF_PASSWORD: "sample",
            CONF_DEVICES: [],
        },
        unique_id="sample@gmail.com",
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.anova.AnovaApi.authenticate"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.anova_precision_cooker_mode")
    assert state is not None
    assert state.state == "idle"

    assert entry.version == 1
    assert entry.minor_version == 2
    assert CONF_DEVICES not in entry.data
