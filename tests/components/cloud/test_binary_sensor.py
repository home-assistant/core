"""Tests for the cloud binary sensor."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from hass_nabucasa.const import DISPATCH_REMOTE_CONNECT, DISPATCH_REMOTE_DISCONNECT
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def mock_wait_until() -> Generator[None, None, None]:
    """Mock WAIT_UNTIL_CHANGE to execute callback immediately."""
    with patch("homeassistant.components.cloud.binary_sensor.WAIT_UNTIL_CHANGE", 0):
        yield


async def test_remote_connection_sensor(
    hass: HomeAssistant,
    cloud: MagicMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test the remote connection sensor."""
    entity_id = "binary_sensor.remote_ui"
    cloud.remote.certificate = None

    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"

    cloud.remote.is_connected = False
    cloud.remote.certificate = object()
    cloud.client.dispatcher_message(DISPATCH_REMOTE_DISCONNECT)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    cloud.remote.is_connected = True
    cloud.client.dispatcher_message(DISPATCH_REMOTE_CONNECT)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Test that a state is not set if the entity is removed.
    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None

    cloud.remote.is_connected = False
    cloud.client.dispatcher_message(DISPATCH_REMOTE_DISCONNECT)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
