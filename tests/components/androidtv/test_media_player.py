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
    STATE_IDLE,
    STATE_OFF,
    STATE_UNAVAILABLE,
)

from . import patchers


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


async def _test_reconnect(hass, caplog, config):
    """Test that the error and reconnection attempts are logged correctly.

    "Handles device/service unavailable. Log a warning once when
    unavailable, log once when reconnected."

    https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
    """
    if CONF_ADB_SERVER_IP not in config[DOMAIN]:
        patch_key = "python"
    else:
        patch_key = "server"

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        entity_id = "media_player.android_tv"
    else:
        entity_id = "media_player.fire_tv"

    with patchers.patch_connect(True)[patch_key], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    caplog.clear()
    caplog.set_level(logging.WARNING)

    with patchers.patch_connect(False)[patch_key], patchers.patch_shell(error=True)[
        patch_key
    ]:
        for _ in range(5):
            await hass.helpers.entity_component.async_update_entity(entity_id)
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

    assert len(caplog.record_tuples) == 2
    assert caplog.record_tuples[0][1] == logging.ERROR
    assert caplog.record_tuples[1][1] == logging.WARNING

    caplog.set_level(logging.DEBUG)
    with patchers.patch_connect(True)[patch_key], patchers.patch_shell("1")[patch_key]:
        # Update 1 will reconnect
        await hass.helpers.entity_component.async_update_entity(entity_id)

        # If using an ADB server, the state will get updated; otherwise, the
        # state will be the last known state
        state = hass.states.get(entity_id)
        if patch_key == "server":
            assert state.state == STATE_IDLE
        else:
            assert state.state == STATE_OFF

        # Update 2 will update the state, regardless of which ADB connection
        # method is used
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_IDLE

    if patch_key == "python":
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


async def _test_adb_shell_returns_none(hass, config):
    """Test the case that the ADB shell command returns `None`.

    The state should be `None` and the device should be unavailable.
    """
    if CONF_ADB_SERVER_IP not in config[DOMAIN]:
        patch_key = "python"
    else:
        patch_key = "server"

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        entity_id = "media_player.android_tv"
    else:
        entity_id = "media_player.fire_tv"

    with patchers.patch_connect(True)[patch_key], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE

    with patchers.patch_shell(None)[patch_key], patchers.patch_shell(error=True)[
        patch_key
    ]:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

    return True


async def test_reconnect_androidtv_python_adb(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly.

    * Device type: Android TV
    * ADB connection method: Python ADB implementation

    """
    assert await _test_reconnect(hass, caplog, CONFIG_ANDROIDTV_PYTHON_ADB)


async def test_adb_shell_returns_none_androidtv_python_adb(hass):
    """Test the case that the ADB shell command returns `None`.

    * Device type: Android TV
    * ADB connection method: Python ADB implementation

    """
    assert await _test_adb_shell_returns_none(hass, CONFIG_ANDROIDTV_PYTHON_ADB)


async def test_reconnect_firetv_python_adb(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly.

    * Device type: Fire TV
    * ADB connection method: Python ADB implementation

    """
    assert await _test_reconnect(hass, caplog, CONFIG_FIRETV_PYTHON_ADB)


async def test_adb_shell_returns_none_firetv_python_adb(hass):
    """Test the case that the ADB shell command returns `None`.

    * Device type: Fire TV
    * ADB connection method: Python ADB implementation

    """
    assert await _test_adb_shell_returns_none(hass, CONFIG_FIRETV_PYTHON_ADB)


async def test_reconnect_androidtv_adb_server(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly.

    * Device type: Android TV
    * ADB connection method: ADB server

    """
    assert await _test_reconnect(hass, caplog, CONFIG_ANDROIDTV_ADB_SERVER)


async def test_adb_shell_returns_none_androidtv_adb_server(hass):
    """Test the case that the ADB shell command returns `None`.

    * Device type: Android TV
    * ADB connection method: ADB server

    """
    assert await _test_adb_shell_returns_none(hass, CONFIG_ANDROIDTV_ADB_SERVER)


async def test_reconnect_firetv_adb_server(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly.

    * Device type: Fire TV
    * ADB connection method: ADB server

    """
    assert await _test_reconnect(hass, caplog, CONFIG_FIRETV_ADB_SERVER)


async def test_adb_shell_returns_none_firetv_adb_server(hass):
    """Test the case that the ADB shell command returns `None`.

    * Device type: Fire TV
    * ADB connection method: ADB server

    """
    assert await _test_adb_shell_returns_none(hass, CONFIG_FIRETV_ADB_SERVER)
