"""Tests for the cloud binary sensor."""
from unittest.mock import Mock

from homeassistant.components.cloud.const import DISPATCHER_REMOTE_UPDATE
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


async def test_remote_connection_sensor(hass):
    """Test the remote connection sensor."""
    assert await async_setup_component(hass, "cloud", {"cloud": {}})
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.remote_ui") is None

    # Fake connection/discovery
    await hass.helpers.discovery.async_load_platform(
        "binary_sensor", "cloud", {}, {"cloud": {}}
    )

    # Mock test env
    cloud = hass.data["cloud"] = Mock()
    cloud.remote.certificate = None
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.remote_ui")
    assert state is not None
    assert state.state == "unavailable"

    with patch("homeassistant.components.cloud.binary_sensor.WAIT_UNTIL_CHANGE", 0):
        cloud.remote.is_connected = False
        cloud.remote.certificate = object()
        hass.helpers.dispatcher.async_dispatcher_send(DISPATCHER_REMOTE_UPDATE, {})
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.remote_ui")
        assert state.state == "off"

        cloud.remote.is_connected = True
        hass.helpers.dispatcher.async_dispatcher_send(DISPATCHER_REMOTE_UPDATE, {})
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.remote_ui")
        assert state.state == "on"
