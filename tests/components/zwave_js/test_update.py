"""Test the Z-Wave JS update entities."""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.version import VersionInfo

from homeassistant.components.update.const import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.util import datetime as dt_util

from .common import DEVICE_CONFIGS_UPDATE_ENTITY

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(name="client_update")
def mock_client_update_fixture(controller_state, version_state, log_config_state):
    """Mock a client."""

    with patch(
        "homeassistant.components.zwave_js.ZwaveClient", autospec=True
    ) as client_class:
        client = client_class.return_value

        async def connect():
            await asyncio.sleep(0)
            client.connected = True

        async def listen(driver_ready: asyncio.Event) -> None:
            driver_ready.set()
            await asyncio.sleep(30)
            assert False, "Listen wasn't canceled!"

        async def disconnect():
            client.connected = False

        client.connect = AsyncMock(side_effect=connect)
        client.listen = AsyncMock(side_effect=listen)
        client.disconnect = AsyncMock(side_effect=disconnect)
        client.driver = Driver(client, controller_state, log_config_state)

        client.version = VersionInfo.from_message(version_state)
        client.ws_server_url = "ws://test:3000/zjs"

        yield client


async def test_config_update_entity(hass, client_update):
    """Test update entity."""
    client_update.async_send_command.return_value = {
        "updateAvailable": False,
    }

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_CONFIGS_UPDATE_ENTITY)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "unknown"
    assert state.attributes[ATTR_LATEST_VERSION] == "unknown"
    assert state.state == STATE_OFF

    client_update.async_send_command.reset_mock()
    client_update.async_send_command.return_value = {
        "updateAvailable": True,
        "newVersion": "1.0.0",
    }

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
    await hass.async_block_till_done()

    state = hass.states.get(DEVICE_CONFIGS_UPDATE_ENTITY)
    assert state
    assert state.attributes[ATTR_INSTALLED_VERSION] == "unknown"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    assert state.state == STATE_ON

    client_update.async_send_command.reset_mock()
    client_update.async_send_command.side_effect = (
        {
            "success": True,
        },
        {"updateAvailable": False},
    )

    # Test successful update call
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: DEVICE_CONFIGS_UPDATE_ENTITY,
        },
        blocking=True,
    )

    assert len(client_update.async_send_command.call_args_list) == 2
    args = client_update.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "driver.install_config_update"
    args = client_update.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "driver.check_for_config_updates"

    client_update.async_send_command.reset_mock()
