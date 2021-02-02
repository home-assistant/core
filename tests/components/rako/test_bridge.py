"""Test the Rako Bridge logic."""
import asyncio
from asyncio.tasks import Task
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from python_rako import RAKO_BRIDGE_DEFAULT_PORT

from homeassistant.components.rako import (
    DATA_RAKO_BRIDGE_CLIENT,
    DATA_RAKO_LIGHT_MAP,
    DATA_RAKO_LISTENER_TASK,
    DOMAIN,
)
from homeassistant.components.rako.bridge import RakoBridge

from . import MOCK_ENTITY_ID, MOCK_HOST


@pytest.fixture
def rako_bridge(hass):
    """Bridge fixture."""
    hass.data[DOMAIN] = {}
    bridge = RakoBridge(MOCK_HOST, RAKO_BRIDGE_DEFAULT_PORT, MOCK_ENTITY_ID, hass)
    hass.data[DOMAIN][MOCK_ENTITY_ID] = {
        DATA_RAKO_BRIDGE_CLIENT: bridge,
        DATA_RAKO_LIGHT_MAP: {},
        DATA_RAKO_LISTENER_TASK: None,
    }
    return bridge


async def test_add_remove_lights(rako_bridge):
    """Test adding and removing lights from being listened for updates. Make sure listener exits cleanly."""
    light1 = SimpleNamespace(unique_id="light1")
    light2 = SimpleNamespace(unique_id="light2")

    async def do_nothing(b):
        assert b == rako_bridge
        while True:
            await asyncio.sleep(1)

    with patch(
        "homeassistant.components.rako.bridge.listen_for_state_updates"
    ) as mock_listen:
        mock_listen.side_effect = do_nothing

        await rako_bridge.register_for_state_updates(light1)
        assert light1 == rako_bridge.get_listening_light(light1.unique_id)
        task: Task = rako_bridge._listener_task

        await rako_bridge.register_for_state_updates(light2)
        assert light2 == rako_bridge.get_listening_light(light2.unique_id)

        await rako_bridge.deregister_for_state_updates(light2)
        assert rako_bridge.get_listening_light(light2.unique_id) is None
        assert task.done() is False

        await rako_bridge.deregister_for_state_updates(light1)
        assert rako_bridge.get_listening_light(light1.unique_id) is None
        assert task.done() is True
