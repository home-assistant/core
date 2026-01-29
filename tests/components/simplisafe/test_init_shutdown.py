"""Test SimpliSafe websocket shutdown behavior."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import CONF_TOKEN, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from homeassistant.components.simplisafe.const import DOMAIN

from tests.common import MockConfigEntry

from .common import REFRESH_TOKEN, USERNAME


@pytest.fixture(name="config")
def config_fixture() -> dict[str, str]:
    """Define config entry data config."""
    return {
        CONF_TOKEN: REFRESH_TOKEN,
        CONF_USERNAME: USERNAME,
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant, config: dict[str, str]
) -> MockConfigEntry:
    """Define a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=USERNAME, data=config
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="websocket")
def websocket_fixture() -> Mock:
    """Define a simplisafe-python websocket object."""
    return Mock(
        async_connect=AsyncMock(),
        async_disconnect=AsyncMock(),
        async_listen=AsyncMock(),
        add_event_callback=Mock(),
    )


@pytest.fixture(name="api")
def api_fixture(
    websocket: Mock, system_v3
) -> Mock:
    """Define a simplisafe-python API object."""
    from simplipy.system.v3 import SystemV3

    return Mock(
        async_get_systems=AsyncMock(return_value={12345: system_v3}),
        refresh_token=REFRESH_TOKEN,
        subscription_data={},
        user_id="12345",
        websocket=websocket,
        add_refresh_token_callback=Mock(),
    )


@pytest.fixture(name="system_v3")
def system_v3_fixture() -> Mock:
    """Define a simplisafe-python V3 System object."""
    from simplipy.system.v3 import SystemV3

    system = Mock(spec=SystemV3)
    system.system_id = 12345
    system.version = 3
    system.address = "Test Base Station"
    system.notifications = []
    system.async_update = AsyncMock()
    system.async_get_latest_event = AsyncMock(return_value={})
    return system


async def test_websocket_cancelled_on_shutdown(
    hass: HomeAssistant, api: Mock, config_entry: MockConfigEntry
) -> None:
    """Test that websocket reconnection task is cancelled on HA shutdown."""
    # Setup the integration
    with (
        patch(
            "homeassistant.components.simplisafe.API.async_from_refresh_token",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.SimpliSafe._async_start_websocket_loop"
        ),
        patch(
            "homeassistant.components.simplisafe.PLATFORMS",
            [],
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the SimpliSafe instance
    simplisafe = hass.data[DOMAIN][config_entry.entry_id]

    # Manually create a websocket task for testing
    async def mock_websocket_loop() -> None:
        """Mock websocket loop that runs until cancelled."""
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    websocket_task = hass.async_create_task(mock_websocket_loop())
    simplisafe._websocket_reconnect_task = websocket_task

    # Verify the websocket task was created and is running
    assert simplisafe._websocket_reconnect_task is not None
    assert not simplisafe._websocket_reconnect_task.done()

    # Fire the HOMEASSISTANT_STOP event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    # Give a moment for the cancellation to propagate
    await asyncio.sleep(0.1)

    # Verify the websocket task was cancelled (it gets set to None after cancellation)
    assert simplisafe._websocket_reconnect_task is None
    assert websocket_task.cancelled()


async def test_websocket_cancelled_on_unload(
    hass: HomeAssistant, api: Mock, config_entry: MockConfigEntry
) -> None:
    """Test that websocket is cancelled when config entry is unloaded."""
    # Setup the integration
    with (
        patch(
            "homeassistant.components.simplisafe.API.async_from_refresh_token",
            return_value=api,
        ),
        patch(
            "homeassistant.components.simplisafe.SimpliSafe._async_start_websocket_loop"
        ),
        patch(
            "homeassistant.components.simplisafe.PLATFORMS",
            [],
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the SimpliSafe instance
    simplisafe = hass.data[DOMAIN][config_entry.entry_id]

    # Manually create a websocket task for testing
    async def mock_websocket_loop() -> None:
        """Mock websocket loop that runs until cancelled."""
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise

    websocket_task = hass.async_create_task(mock_websocket_loop())
    simplisafe._websocket_reconnect_task = websocket_task

    # Verify the websocket task was created
    assert simplisafe._websocket_reconnect_task is not None

    # Unload the config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the websocket task was cancelled (it gets set to None after cancellation)
    assert websocket_task.cancelled()
