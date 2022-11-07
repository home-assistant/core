"""The tests for Kodi binary sensor platform."""
from unittest.mock import patch

from jsonrpc_base.jsonrpc import TransportError
import pytest

from homeassistant.components.kodi.const import WS_DPMS, WS_SCREENSAVER
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import (
    PATCH_KODI_BINARY,
    PATCH_KODI_CONNMAN,
    PATCH_KODI_MEDIA,
    init_integration,
    stop_integration,
)


@pytest.mark.parametrize(
    "element, name",
    [(WS_SCREENSAVER["id"], WS_SCREENSAVER["name"]), (WS_DPMS["id"], WS_DPMS["name"])],
)
async def test_binary_sensor_initial_states(hass: HomeAssistant, element, name):
    """Test for binary sensor values."""
    entry = await init_integration(hass)

    state = hass.states.get(f"binary_sensor.{entry.data['name']}_{element}")
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == f"{entry.data['name']} {name}"


async def test_binary_sensor_websocket_connect(hass: HomeAssistant):
    """Test basic websocket connect procedure."""
    with patch(  # Catching all websocket callbacks
        f"{PATCH_KODI_CONNMAN}.register_websocket_callback", return_value=True
    ) as mock_callbacks, patch(  # To start connman without errors
        "pykodi.Kodi.get_application_properties",
        return_value={"version": {"major": 1, "minor": 1}},
    ) as mock_kodi_version:
        await init_integration(hass, True, False)

    # Kodi version is retrieved
    mock_kodi_version.assert_called_once_with(["version"])
    # KodiConnectionManager ws callbacks are registered
    assert 3 == mock_callbacks.call_count

    await stop_integration(hass)


@pytest.mark.parametrize(
    "element, method_on, method_off",
    [
        (WS_SCREENSAVER["id"], WS_SCREENSAVER["on"], WS_SCREENSAVER["off"]),
        (WS_DPMS["id"], WS_DPMS["on"], WS_DPMS["off"]),
    ],
)
async def test_binary_sensor_websocket_update(
    hass: HomeAssistant, element, method_on, method_off
):
    """Test binary sensor value change via websocket callbacks."""
    with patch(  # Catching all websocket callbacks
        f"{PATCH_KODI_CONNMAN}.register_websocket_callback", return_value=True
    ) as mock_callbacks, patch(  # Skip errors in media_plyer update for binary sensor tests
        f"{PATCH_KODI_MEDIA}.KodiEntity.async_update", return_value=True
    ) as mock_media_update, patch(  # Init binary sensors true
        "pykodi.Kodi.call_method",
        return_value={WS_SCREENSAVER["boolean"]: True, WS_DPMS["boolean"]: True},
    ) as mock_init_sensor:
        entry = await init_integration(hass, True, True)

    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    # One instance of media_player
    assert 1 == mock_media_update.call_count
    # Two instances of binary_sensor
    assert 2 == mock_init_sensor.call_count

    for callarg in mock_callbacks.call_args_list:
        if callarg[0][0] == method_on:
            callback_on = callarg[0][1]
        if callarg[0][0] == method_off:
            callback_off = callarg[0][1]

    # Test if callbacks are found
    assert callback_on
    assert callback_off

    # Initial state of the sensors is on (see patch above)
    assert hass.states.get(entity_id).state == STATE_ON

    callback_off("test", "test")
    assert hass.states.get(entity_id).state == STATE_OFF

    callback_on("test", "test")
    assert hass.states.get(entity_id).state == STATE_ON

    await stop_integration(hass)


@pytest.mark.parametrize(
    "element, boolean",
    [
        (WS_SCREENSAVER["id"], WS_SCREENSAVER["boolean"]),
        (WS_DPMS["id"], WS_DPMS["boolean"]),
    ],
)
async def test_binary_sensor_poll_update(hass: HomeAssistant, element, boolean):
    """Test the async_update method."""
    entry = await init_integration(hass, False, True)
    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    # Test connection online, response OK, True
    with patch("pykodi.Kodi.call_method", return_value={boolean: True}):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # Test connection online, response OK, False
    with patch("pykodi.Kodi.call_method", return_value={boolean: False}):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # Force the state to on for the next tests
    hass.states.async_set(entity_id, STATE_ON)

    # Test connection online, response empty
    with patch("pykodi.Kodi.call_method", return_value=None):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # Force the state to on for the next tests
    hass.states.async_set(entity_id, STATE_ON)

    # Test connection online, TransportError caught in async_update
    with patch("pykodi.Kodi.call_method", side_effect=TransportError("Test")), patch(
        f"{PATCH_KODI_BINARY}._reset_state"
    ) as mock_reset:
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()
    mock_reset.assert_called_once_with()
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "element, boolean",
    [
        (WS_SCREENSAVER["id"], WS_SCREENSAVER["boolean"]),
        (WS_DPMS["id"], WS_DPMS["boolean"]),
    ],
)
async def test_binary_sensor_poll_update_offline(hass: HomeAssistant, element, boolean):
    """Test the async_update method."""
    # HTTP Connection, not connected
    entry = await init_integration(hass, False, False)
    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    with patch("pykodi.Kodi.call_method", return_value={boolean: True}):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF
