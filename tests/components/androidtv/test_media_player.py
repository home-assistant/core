"""The tests for the androidtv platform."""
import logging

from homeassistant.setup import async_setup_component
from homeassistant.components.androidtv.media_player import (
    ANDROIDTV_DOMAIN,
    CONF_ADB_SERVER_IP,
)
from homeassistant.components.media_player.const import DOMAIN
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_UNAVAILABLE,
)

from . import patchers


ENTITY_ID_ANDROIDTV = "media_player.android_tv"
ENTITY_ID_FIRETV = "media_player.fire_tv"

# Android TV device with Python ADB implementation
CONFIG_ANDROIDTV_PYTHON_ADB = {
    DOMAIN: {
        CONF_PLATFORM: ANDROIDTV_DOMAIN,
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Android TV",
    }
}

# Android TV device with ADB server
CONFIG_ANDROIDTV_ADB_SERVER = {
    DOMAIN: {
        CONF_PLATFORM: ANDROIDTV_DOMAIN,
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Android TV",
        CONF_ADB_SERVER_IP: "127.0.0.1",
    }
}

# Fire TV device with Python ADB implementation
CONFIG_FIRETV_PYTHON_ADB = {
    DOMAIN: {
        CONF_PLATFORM: ANDROIDTV_DOMAIN,
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Fire TV",
        CONF_DEVICE_CLASS: "firetv",
    }
}

# Fire TV device with ADB server
CONFIG_FIRETV_ADB_SERVER = {
    DOMAIN: {
        CONF_PLATFORM: ANDROIDTV_DOMAIN,
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Fire TV",
        CONF_DEVICE_CLASS: "firetv",
        CONF_ADB_SERVER_IP: "127.0.0.1",
    }
}


async def _test_reconnect(
    hass,
    caplog,
    config,
    entity_id,
    patch_connect_success,
    patch_command_success,
    patch_connnect_fail,
    patch_command_fail,
):
    """Test that the error and reconnection attempts are logged correctly.

    "Handles device/service unavailable. Log a warning once when
    unavailable, log once when reconnected."

    https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
    """
    with patch_connect_success, patch_command_success:
        assert await async_setup_component(hass, DOMAIN, config)

    caplog.clear()
    caplog.set_level(logging.WARNING)

    with patch_connnect_fail, patch_command_fail:
        for _ in range(5):
            await hass.helpers.entity_component.async_update_entity(entity_id)
            state = hass.states.get(entity_id)
            assert state.state == STATE_UNAVAILABLE
            # assert not state.attributes["available"]

    assert len(caplog.record_tuples) == 2

    caplog.set_level(logging.DEBUG)
    with patch_connect_success, patch_command_success:
        # Update 1 will reconnect
        await hass.helpers.entity_component.async_update_entity(entity_id)
        # state = hass.states.get(entity_id)
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

        # Update 2 will update the state
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state.state != STATE_UNAVAILABLE
        # assert state.attributes["available"]

    if CONF_ADB_SERVER_IP not in config[DOMAIN]:
        assert (
            "ADB connection to 127.0.0.1:5555 successfully established"
            in caplog.record_tuples[2]
        )
    else:
        assert (
            "ADB connection to 127.0.0.1:5555 via ADB server 127.0.0.1:5037 successfully established"
            in caplog.record_tuples[2]
        )

    return True


async def _test_adb_shell_returns_none(
    hass,
    config,
    entity_id,
    patch_connect_success,
    patch_command_success,
    patch_command_none,
):
    """Test the case that the ADB shell command returns `None`.

    The state should be `None` and the device should be unavailable.
    """
    with patch_connect_success, patch_command_success:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    with patch_command_none:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    return True


async def test_reconnect_androidtv_python_adb(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly."""

    assert await _test_reconnect(
        hass,
        caplog,
        CONFIG_ANDROIDTV_PYTHON_ADB,
        ENTITY_ID_ANDROIDTV,
        patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS,
        patchers.PATCH_PYTHON_ADB_CONNECT_FAIL,
        patchers.PATCH_PYTHON_ADB_COMMAND_FAIL,
    )


async def test_adb_shell_returns_none_androidtv_python_adb(hass):
    """Test the case that the ADB shell command returns `None`."""

    assert await _test_adb_shell_returns_none(
        hass,
        CONFIG_ANDROIDTV_PYTHON_ADB,
        ENTITY_ID_ANDROIDTV,
        patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_NONE,
    )


async def test_reconnect_firetv_python_adb(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly."""

    assert await _test_reconnect(
        hass,
        caplog,
        CONFIG_FIRETV_PYTHON_ADB,
        ENTITY_ID_FIRETV,
        patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS,
        patchers.PATCH_PYTHON_ADB_CONNECT_FAIL,
        patchers.PATCH_PYTHON_ADB_COMMAND_FAIL,
    )


async def test_adb_shell_returns_none_firetv_python_adb(hass):
    """Test the case that the ADB shell command returns `None`."""

    assert await _test_adb_shell_returns_none(
        hass,
        CONFIG_FIRETV_PYTHON_ADB,
        ENTITY_ID_FIRETV,
        patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_NONE,
    )


async def test_reconnect_androidtv_adb_server(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly."""

    assert await _test_reconnect(
        hass,
        caplog,
        CONFIG_ANDROIDTV_ADB_SERVER,
        ENTITY_ID_ANDROIDTV,
        patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS,
        patchers.PATCH_ADB_SERVER_AVAILABLE,
        patchers.PATCH_ADB_SERVER_CONNECT_FAIL,
        patchers.PATCH_ADB_SERVER_COMMAND_FAIL,
    )


async def test_adb_shell_returns_none_androidtv_adb_server(hass):
    """Test the case that the ADB shell command returns `None`."""

    assert await _test_adb_shell_returns_none(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        ENTITY_ID_ANDROIDTV,
        patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS,
        patchers.PATCH_ADB_SERVER_AVAILABLE,
        patchers.PATCH_ADB_SERVER_COMMAND_NONE,
    )


async def test_reconnect_firetv_adb_server(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly."""

    assert await _test_reconnect(
        hass,
        caplog,
        CONFIG_FIRETV_ADB_SERVER,
        ENTITY_ID_FIRETV,
        patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS,
        patchers.PATCH_ADB_SERVER_AVAILABLE,
        patchers.PATCH_ADB_SERVER_CONNECT_FAIL,
        patchers.PATCH_ADB_SERVER_COMMAND_FAIL,
    )


async def test_adb_shell_returns_none_firetv_adb_server(hass):
    """Test the case that the ADB shell command returns `None`."""

    assert await _test_adb_shell_returns_none(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        ENTITY_ID_FIRETV,
        patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS,
        patchers.PATCH_ADB_SERVER_AVAILABLE,
        patchers.PATCH_ADB_SERVER_COMMAND_NONE,
    )
