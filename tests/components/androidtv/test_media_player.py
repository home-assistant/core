"""The tests for the androidtv platform."""
import logging

from homeassistant.components.androidtv.media_player import (
    ANDROIDTV_DOMAIN,
    CONF_ADB_SERVER_IP,
    CONF_ADBKEY,
    CONF_APPS,
)
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component

from . import patchers

# Android TV device with Python ADB implementation
CONFIG_ANDROIDTV_PYTHON_ADB = {
    DOMAIN: {
        CONF_PLATFORM: ANDROIDTV_DOMAIN,
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Android TV",
        CONF_DEVICE_CLASS: "androidtv",
    }
}

# Android TV device with ADB server
CONFIG_ANDROIDTV_ADB_SERVER = {
    DOMAIN: {
        CONF_PLATFORM: ANDROIDTV_DOMAIN,
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "Android TV",
        CONF_DEVICE_CLASS: "androidtv",
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


def _setup(hass, config):
    """Perform common setup tasks for the tests."""
    if CONF_ADB_SERVER_IP not in config[DOMAIN]:
        patch_key = "python"
    else:
        patch_key = "server"

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        entity_id = "media_player.android_tv"
    else:
        entity_id = "media_player.fire_tv"

    return patch_key, entity_id


async def _test_reconnect(hass, caplog, config):
    """Test that the error and reconnection attempts are logged correctly.

    "Handles device/service unavailable. Log a warning once when
    unavailable, log once when reconnected."

    https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
    """
    patch_key, entity_id = _setup(hass, config)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        assert await async_setup_component(hass, DOMAIN, config)

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    caplog.clear()
    caplog.set_level(logging.WARNING)

    with patchers.patch_connect(False)[patch_key], patchers.patch_shell(error=True)[
        patch_key
    ], patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        for _ in range(5):
            await hass.helpers.entity_component.async_update_entity(entity_id)
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

    assert len(caplog.record_tuples) == 2
    assert caplog.record_tuples[0][1] == logging.ERROR
    assert caplog.record_tuples[1][1] == logging.WARNING

    caplog.set_level(logging.DEBUG)
    with patchers.patch_connect(True)[patch_key], patchers.patch_shell("1")[
        patch_key
    ], patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
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
    patch_key, entity_id = _setup(hass, config)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE

    with patchers.patch_shell(None)[patch_key], patchers.patch_shell(error=True)[
        patch_key
    ], patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
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


async def test_setup_with_adbkey(hass):
    """Test that setup succeeds when using an ADB key."""
    config = CONFIG_ANDROIDTV_PYTHON_ADB.copy()
    config[DOMAIN][CONF_ADBKEY] = hass.config.path("user_provided_adbkey")
    patch_key, entity_id = _setup(hass, config)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[
        patch_key
    ], patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER, patchers.PATCH_ISFILE, patchers.PATCH_ACCESS:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF


async def _test_sources(hass, config0):
    """Test that sources (i.e., apps) are handled correctly for Android TV and Fire TV devices."""
    config = config0.copy()
    config[DOMAIN][CONF_APPS] = {"com.app.test1": "TEST 1"}
    patch_key, entity_id = _setup(hass, config)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        patch_update = patchers.patch_androidtv_update(
            "playing",
            "com.app.test1",
            ["com.app.test1", "com.app.test2"],
            "hdmi",
            False,
            1,
        )
    else:
        patch_update = patchers.patch_firetv_update(
            "playing", "com.app.test1", ["com.app.test1", "com.app.test2"]
        )

    with patch_update:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "TEST 1"
        assert state.attributes["source_list"] == ["TEST 1", "com.app.test2"]

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        patch_update = patchers.patch_androidtv_update(
            "playing",
            "com.app.test2",
            ["com.app.test2", "com.app.test1"],
            "hdmi",
            True,
            0,
        )
    else:
        patch_update = patchers.patch_firetv_update(
            "playing", "com.app.test2", ["com.app.test2", "com.app.test1"]
        )

    with patch_update:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "com.app.test2"
        assert state.attributes["source_list"] == ["com.app.test2", "TEST 1"]

    return True


async def test_androidtv_sources(hass):
    """Test that sources (i.e., apps) are handled correctly for Android TV devices."""
    assert await _test_sources(hass, CONFIG_ANDROIDTV_ADB_SERVER)


async def test_firetv_sources(hass):
    """Test that sources (i.e., apps) are handled correctly for Fire TV devices."""
    assert await _test_sources(hass, CONFIG_FIRETV_ADB_SERVER)


async def _test_select_source(hass, config0, source, expected_arg, method_patch):
    """Test that the methods for launching and stopping apps are called correctly when selecting a source."""
    config = config0.copy()
    config[DOMAIN][CONF_APPS] = {"com.app.test1": "TEST 1"}
    patch_key, entity_id = _setup(hass, config)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with method_patch as method_patch_:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: entity_id, ATTR_INPUT_SOURCE: source},
            blocking=True,
        )
        method_patch_.assert_called_with(expected_arg)

    return True


async def test_androidtv_select_source_launch_app_id(hass):
    """Test that an app can be launched using its app ID."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "com.app.test1",
        "com.app.test1",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_androidtv_select_source_launch_app_name(hass):
    """Test that an app can be launched using its friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "TEST 1",
        "com.app.test1",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_androidtv_select_source_launch_app_id_no_name(hass):
    """Test that an app can be launched using its app ID when it has no friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "com.app.test2",
        "com.app.test2",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_androidtv_select_source_stop_app_id(hass):
    """Test that an app can be stopped using its app ID."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "!com.app.test1",
        "com.app.test1",
        patchers.PATCH_STOP_APP,
    )


async def test_androidtv_select_source_stop_app_name(hass):
    """Test that an app can be stopped using its friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "!TEST 1",
        "com.app.test1",
        patchers.PATCH_STOP_APP,
    )


async def test_androidtv_select_source_stop_app_id_no_name(hass):
    """Test that an app can be stopped using its app ID when it has no friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "!com.app.test2",
        "com.app.test2",
        patchers.PATCH_STOP_APP,
    )


async def test_firetv_select_source_launch_app_id(hass):
    """Test that an app can be launched using its app ID."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "com.app.test1",
        "com.app.test1",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_firetv_select_source_launch_app_name(hass):
    """Test that an app can be launched using its friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "TEST 1",
        "com.app.test1",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_firetv_select_source_launch_app_id_no_name(hass):
    """Test that an app can be launched using its app ID when it has no friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "com.app.test2",
        "com.app.test2",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_firetv_select_source_stop_app_id(hass):
    """Test that an app can be stopped using its app ID."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "!com.app.test1",
        "com.app.test1",
        patchers.PATCH_STOP_APP,
    )


async def test_firetv_select_source_stop_app_name(hass):
    """Test that an app can be stopped using its friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "!TEST 1",
        "com.app.test1",
        patchers.PATCH_STOP_APP,
    )


async def test_firetv_select_source_stop_app_id_no_name(hass):
    """Test that an app can be stopped using its app ID when it has no friendly name."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "!com.app.test2",
        "com.app.test2",
        patchers.PATCH_STOP_APP,
    )


async def _test_setup_fail(hass, config):
    """Test that the entity is not created when the ADB connection is not established."""
    patch_key, entity_id = _setup(hass, config)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(False)[
        patch_key
    ], patchers.patch_shell("")[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is None

    return True


async def test_setup_fail_androidtv(hass):
    """Test that the Android TV entity is not created when the ADB connection is not established."""
    assert await _test_setup_fail(hass, CONFIG_ANDROIDTV_PYTHON_ADB)


async def test_setup_fail_firetv(hass):
    """Test that the Fire TV entity is not created when the ADB connection is not established."""
    assert await _test_setup_fail(hass, CONFIG_FIRETV_PYTHON_ADB)


async def test_setup_two_devices(hass):
    """Test that two devices can be set up."""
    config = {
        DOMAIN: [
            CONFIG_ANDROIDTV_ADB_SERVER[DOMAIN],
            CONFIG_FIRETV_ADB_SERVER[DOMAIN].copy(),
        ]
    }
    config[DOMAIN][1][CONF_HOST] = "127.0.0.2"

    patch_key = "server"
    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, config)

        for entity_id in ["media_player.android_tv", "media_player.fire_tv"]:
            await hass.helpers.entity_component.async_update_entity(entity_id)
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == STATE_OFF


async def test_setup_same_device_twice(hass):
    """Test that setup succeeds with a duplicated config entry."""
    patch_key = "server"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, CONFIG_ANDROIDTV_ADB_SERVER)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell("")[patch_key]:
        assert await async_setup_component(hass, DOMAIN, CONFIG_ANDROIDTV_ADB_SERVER)
