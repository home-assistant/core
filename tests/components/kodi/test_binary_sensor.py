"""The tests for Kodi binary sensor platform."""
from unittest.mock import patch

from jsonrpc_base.jsonrpc import TransportError
import pytest

from homeassistant.components.kodi.const import WS_DPMS, WS_SCREENSAVER
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import stop_integration


@pytest.mark.parametrize(
    "element, name",
    [(WS_SCREENSAVER["id"], WS_SCREENSAVER["name"]), (WS_DPMS["id"], WS_DPMS["name"])],
)
async def test_binary_sensor_initial_states(
    hass: HomeAssistant, element, name, kodi_connection
):
    """Test for initial binary sensor values."""
    entry = kodi_connection

    state = hass.states.get(f"binary_sensor.{entry.data['name']}_{element}")
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == f"{entry.data['name']} {name}"


@pytest.mark.use_websocket
async def test_binary_sensor_websocket_connect(
    # pylint: disable=unused-argument
    hass: HomeAssistant,
    mock_ws_callbacks,
    mock_kodi_version,
    kodi_connection,
):
    """Test basic websocket connect procedure."""

    # Kodi version is retrieved
    mock_kodi_version.assert_called_once_with(["version"])
    # KodiConnectionManager ws callbacks are registered
    assert 3 == mock_ws_callbacks.call_count

    await stop_integration(hass)


@pytest.mark.parametrize(
    "element, method_on, method_off",
    [
        (WS_SCREENSAVER["id"], WS_SCREENSAVER["on"], WS_SCREENSAVER["off"]),
        (WS_DPMS["id"], WS_DPMS["on"], WS_DPMS["off"]),
    ],
)
@pytest.mark.use_websocket
@pytest.mark.connected
async def test_binary_sensor_websocket_update(
    hass: HomeAssistant,
    element,
    method_on,
    method_off,
    mock_ws_callbacks,
    mock_sensors_init,
    kodi_connection,
):
    """Test binary sensor value change via websocket callbacks."""
    entry = kodi_connection

    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    # Two instances of binary_sensor
    assert 2 == mock_sensors_init.call_count

    for callarg in mock_ws_callbacks.call_args_list:
        if callarg[0][0] == method_on:
            callback_on = callarg[0][1]
        if callarg[0][0] == method_off:
            callback_off = callarg[0][1]

    # Test if callbacks are found
    assert callback_on
    assert callback_off

    # Initial state of the sensors is on (see mock_sensors_init)
    assert hass.states.get(entity_id).state == STATE_ON

    callback_off("test", "test")
    assert hass.states.get(entity_id).state == STATE_OFF

    callback_on("test", "test")
    assert hass.states.get(entity_id).state == STATE_ON

    await stop_integration(hass)


async def _test_sensor_poll(
    hass: HomeAssistant, entity_id: str, boolean: str, inject: bool, expect: str
):
    """Inject an assert a sensor state after async_update."""
    if inject is None:
        retval = None
    else:
        retval = {boolean: inject}

    with patch("pykodi.Kodi.call_method", return_value=retval):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expect


@pytest.mark.parametrize(
    "element, boolean",
    [
        (WS_SCREENSAVER["id"], WS_SCREENSAVER["boolean"]),
        (WS_DPMS["id"], WS_DPMS["boolean"]),
    ],
)
@pytest.mark.connected
async def test_binary_sensor_poll_update(
    hass: HomeAssistant, element, boolean, kodi_connection
):
    """Test the async_update method when connection is online."""
    entry = kodi_connection
    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    # Test connection online, response OK, True
    await _test_sensor_poll(hass, entity_id, boolean, True, STATE_ON)

    # Test connection online, response OK, False
    await _test_sensor_poll(hass, entity_id, boolean, False, STATE_OFF)

    # Force the state to on for the next test
    hass.states.async_set(entity_id, STATE_ON)

    # Test connection online, response empty
    await _test_sensor_poll(hass, entity_id, boolean, None, STATE_OFF)

    # Force the state to on for the next test
    hass.states.async_set(entity_id, STATE_ON)

    # Test connection online, TransportError caught in async_update
    with patch("pykodi.Kodi.call_method", side_effect=TransportError("Test")):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "element, boolean",
    [
        (WS_SCREENSAVER["id"], WS_SCREENSAVER["boolean"]),
        (WS_DPMS["id"], WS_DPMS["boolean"]),
    ],
)
async def test_binary_sensor_poll_update_offline(
    hass: HomeAssistant, element, boolean, kodi_connection
):
    """Test the async_update method when connection is offline."""
    # HTTP Connection, not connected
    entry = kodi_connection
    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    await _test_sensor_poll(hass, entity_id, boolean, True, STATE_OFF)
