"""The tests for the androidtv platform."""
import base64
import copy
import logging
from unittest.mock import patch

from androidtv.constants import APPS as ANDROIDTV_APPS, KEYS
from androidtv.exceptions import LockNotAcquiredException
import pytest

from homeassistant.components.androidtv.const import (
    CONF_ADB_SERVER_IP,
    CONF_ADB_SERVER_PORT,
    CONF_ADBKEY,
    CONF_APPS,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_TURN_OFF_COMMAND,
    CONF_TURN_ON_COMMAND,
    DEFAULT_ADB_SERVER_PORT,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.androidtv.media_player import (
    ATTR_DEVICE_PATH,
    ATTR_LOCAL_PATH,
    SERVICE_ADB_COMMAND,
    SERVICE_DOWNLOAD,
    SERVICE_LEARN_SENDEVENT,
    SERVICE_UPLOAD,
)
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SELECT_SOURCE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
)
from homeassistant.util import slugify

from tests.common import MockConfigEntry
from tests.components.androidtv import patchers

CONF_OPTIONS = "options"

PATCH_ACCESS = patch("homeassistant.components.androidtv.os.access", return_value=True)
PATCH_ISFILE = patch(
    "homeassistant.components.androidtv.os.path.isfile", patchers.isfile
)

SHELL_RESPONSE_OFF = ""
SHELL_RESPONSE_STANDBY = "1"

# Android TV device with Python ADB implementation
CONFIG_ANDROIDTV_PYTHON_ADB = {
    DOMAIN: {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: "androidtv",
        CONF_ADB_SERVER_PORT: DEFAULT_ADB_SERVER_PORT,
    }
}

# Android TV device with ADB server
CONFIG_ANDROIDTV_ADB_SERVER = {
    DOMAIN: {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: "androidtv",
        CONF_ADB_SERVER_IP: "127.0.0.1",
        CONF_ADB_SERVER_PORT: DEFAULT_ADB_SERVER_PORT,
    }
}

# Fire TV device with Python ADB implementation
CONFIG_FIRETV_PYTHON_ADB = {
    DOMAIN: {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: "firetv",
        CONF_ADB_SERVER_PORT: DEFAULT_ADB_SERVER_PORT,
    }
}

# Fire TV device with ADB server
CONFIG_FIRETV_ADB_SERVER = {
    DOMAIN: {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE_CLASS: "firetv",
        CONF_ADB_SERVER_IP: "127.0.0.1",
        CONF_ADB_SERVER_PORT: DEFAULT_ADB_SERVER_PORT,
    }
}


def _setup(config):
    """Perform common setup tasks for the tests."""
    if CONF_ADB_SERVER_IP not in config[DOMAIN]:
        patch_key = "python"
    else:
        patch_key = "server"

    host = config[DOMAIN][CONF_HOST]
    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        entity_id = slugify(f"Android TV {host}")
    else:
        entity_id = slugify(f"Fire TV {host}")
    entity_id = f"{MP_DOMAIN}.{entity_id}"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=config[DOMAIN],
        unique_id="a1:b1:c1:d1:e1:f1",
        options=config[DOMAIN].get(CONF_OPTIONS),
    )

    return patch_key, entity_id, config_entry


async def test_setup_with_properties(hass):
    """Test that setup succeeds with device properties.

    the response must be a string with the following info separated with line break:
    "manufacturer, model, serialno, version, mac_wlan0_output, mac_eth0_output"

    """

    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    response = "fake\nfake\n0123456\nfake\nether a1:b1:c1:d1:e1:f1 brd\nnone"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(response)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None


@pytest.mark.parametrize(
    "config",
    [
        CONFIG_ANDROIDTV_PYTHON_ADB,
        CONFIG_FIRETV_PYTHON_ADB,
        CONFIG_ANDROIDTV_ADB_SERVER,
        CONFIG_FIRETV_ADB_SERVER,
    ],
)
async def test_reconnect(hass, caplog, config):
    """Test that the error and reconnection attempts are logged correctly.

    "Handles device/service unavailable. Log a warning once when
    unavailable, log once when reconnected."

    https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
    """
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

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
    with patchers.patch_connect(True)[patch_key], patchers.patch_shell(
        SHELL_RESPONSE_STANDBY
    )[patch_key], patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        await hass.helpers.entity_component.async_update_entity(entity_id)

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_STANDBY

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


@pytest.mark.parametrize(
    "config",
    [
        CONFIG_ANDROIDTV_PYTHON_ADB,
        CONFIG_FIRETV_PYTHON_ADB,
        CONFIG_ANDROIDTV_ADB_SERVER,
        CONFIG_FIRETV_ADB_SERVER,
    ],
)
async def test_adb_shell_returns_none(hass, config):
    """Test the case that the ADB shell command returns `None`.

    The state should be `None` and the device should be unavailable.
    """
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

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


async def test_setup_with_adbkey(hass):
    """Test that setup succeeds when using an ADB key."""
    config = copy.deepcopy(CONFIG_ANDROIDTV_PYTHON_ADB)
    config[DOMAIN][CONF_ADBKEY] = hass.config.path("user_provided_adbkey")
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[
        patch_key
    ], patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER, PATCH_ISFILE, PATCH_ACCESS:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "config0",
    [
        CONFIG_ANDROIDTV_ADB_SERVER,
        CONFIG_FIRETV_ADB_SERVER,
    ],
)
async def test_sources(hass, config0):
    """Test that sources (i.e., apps) are handled correctly for Android TV and Fire TV devices."""
    config = copy.deepcopy(config0)
    config[DOMAIN].setdefault(CONF_OPTIONS, {}).update(
        {
            CONF_APPS: {
                "com.app.test1": "TEST 1",
                "com.app.test3": None,
                "com.app.test4": SHELL_RESPONSE_OFF,
            }
        }
    )
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        patch_update = patchers.patch_androidtv_update(
            "playing",
            "com.app.test1",
            ["com.app.test1", "com.app.test2", "com.app.test3", "com.app.test4"],
            "hdmi",
            False,
            1,
            "HW5",
        )
    else:
        patch_update = patchers.patch_firetv_update(
            "playing",
            "com.app.test1",
            ["com.app.test1", "com.app.test2", "com.app.test3", "com.app.test4"],
            "HW5",
        )

    with patch_update:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "TEST 1"
        assert sorted(state.attributes["source_list"]) == ["TEST 1", "com.app.test2"]

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        patch_update = patchers.patch_androidtv_update(
            "playing",
            "com.app.test2",
            ["com.app.test2", "com.app.test1", "com.app.test3", "com.app.test4"],
            "hdmi",
            True,
            0,
            "HW5",
        )
    else:
        patch_update = patchers.patch_firetv_update(
            "playing",
            "com.app.test2",
            ["com.app.test2", "com.app.test1", "com.app.test3", "com.app.test4"],
            "HW5",
        )

    with patch_update:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "com.app.test2"
        assert sorted(state.attributes["source_list"]) == ["TEST 1", "com.app.test2"]


async def _test_exclude_sources(hass, config0, expected_sources):
    """Test that sources (i.e., apps) are handled correctly when the `exclude_unnamed_apps` config parameter is provided."""
    config = copy.deepcopy(config0)
    config[DOMAIN].setdefault(CONF_OPTIONS, {}).update(
        {
            CONF_APPS: {
                "com.app.test1": "TEST 1",
                "com.app.test3": None,
                "com.app.test4": SHELL_RESPONSE_OFF,
            }
        }
    )
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    if config[DOMAIN].get(CONF_DEVICE_CLASS) != "firetv":
        patch_update = patchers.patch_androidtv_update(
            "playing",
            "com.app.test1",
            [
                "com.app.test1",
                "com.app.test2",
                "com.app.test3",
                "com.app.test4",
                "com.app.test5",
            ],
            "hdmi",
            False,
            1,
            "HW5",
        )
    else:
        patch_update = patchers.patch_firetv_update(
            "playing",
            "com.app.test1",
            [
                "com.app.test1",
                "com.app.test2",
                "com.app.test3",
                "com.app.test4",
                "com.app.test5",
            ],
            "HW5",
        )

    with patch_update:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "TEST 1"
        assert sorted(state.attributes["source_list"]) == expected_sources

    return True


async def test_androidtv_exclude_sources(hass):
    """Test that sources (i.e., apps) are handled correctly for Android TV devices when the `exclude_unnamed_apps` config parameter is provided as true."""
    config = copy.deepcopy(CONFIG_ANDROIDTV_ADB_SERVER)
    config[DOMAIN][CONF_OPTIONS] = {CONF_EXCLUDE_UNNAMED_APPS: True}
    assert await _test_exclude_sources(hass, config, ["TEST 1"])


async def test_firetv_exclude_sources(hass):
    """Test that sources (i.e., apps) are handled correctly for Fire TV devices when the `exclude_unnamed_apps` config parameter is provided as true."""
    config = copy.deepcopy(CONFIG_FIRETV_ADB_SERVER)
    config[DOMAIN][CONF_OPTIONS] = {CONF_EXCLUDE_UNNAMED_APPS: True}
    assert await _test_exclude_sources(hass, config, ["TEST 1"])


async def _test_select_source(hass, config0, source, expected_arg, method_patch):
    """Test that the methods for launching and stopping apps are called correctly when selecting a source."""
    config = copy.deepcopy(config0)
    config[DOMAIN].setdefault(CONF_OPTIONS, {}).update(
        {
            CONF_APPS: {
                "com.app.test1": "TEST 1",
                "com.app.test3": None,
                "com.youtube.test": "YouTube",
            }
        }
    )
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with method_patch as method_patch_:
        await hass.services.async_call(
            MP_DOMAIN,
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


async def test_androidtv_select_source_launch_app_hidden(hass):
    """Test that an app can be launched using its app ID when it is hidden from the sources list."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "com.app.test3",
        "com.app.test3",
        patchers.PATCH_LAUNCH_APP,
    )


async def test_androidtv_select_source_overridden_app_name(hass):
    """Test that when an app name is overridden via the `apps` configuration parameter, the app is launched correctly."""
    # Evidence that the default YouTube app ID will be overridden
    assert "YouTube" in ANDROIDTV_APPS.values()
    assert "com.youtube.test" not in ANDROIDTV_APPS
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "YouTube",
        "com.youtube.test",
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


async def test_androidtv_select_source_stop_app_hidden(hass):
    """Test that an app can be stopped using its app ID when it is hidden from the sources list."""
    assert await _test_select_source(
        hass,
        CONFIG_ANDROIDTV_ADB_SERVER,
        "!com.app.test3",
        "com.app.test3",
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


async def test_firetv_select_source_launch_app_hidden(hass):
    """Test that an app can be launched using its app ID when it is hidden from the sources list."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "com.app.test3",
        "com.app.test3",
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


async def test_firetv_select_source_stop_hidden(hass):
    """Test that an app can be stopped using its app ID when it is hidden from the sources list."""
    assert await _test_select_source(
        hass,
        CONFIG_FIRETV_ADB_SERVER,
        "!com.app.test3",
        "com.app.test3",
        patchers.PATCH_STOP_APP,
    )


@pytest.mark.parametrize(
    "config",
    [
        CONFIG_ANDROIDTV_PYTHON_ADB,
        CONFIG_FIRETV_PYTHON_ADB,
    ],
)
async def test_setup_fail(hass, config):
    """Test that the entity is not created when the ADB connection is not established."""
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(False)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id) is False
            await hass.async_block_till_done()

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is None


async def test_adb_command(hass):
    """Test sending a command via the `androidtv.adb_command` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    command = "test command"
    response = "test response"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_shell", return_value=response
        ) as patch_shell:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADB_COMMAND,
                {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: command},
                blocking=True,
            )

            patch_shell.assert_called_with(command)
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.attributes["adb_response"] == response


async def test_adb_command_unicode_decode_error(hass):
    """Test sending a command via the `androidtv.adb_command` service that raises a UnicodeDecodeError exception."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    command = "test command"
    response = b"test response"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_shell",
            side_effect=UnicodeDecodeError("utf-8", response, 0, len(response), "TEST"),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADB_COMMAND,
                {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: command},
                blocking=True,
            )

            state = hass.states.get(entity_id)
            assert state is not None
            assert state.attributes["adb_response"] is None


async def test_adb_command_key(hass):
    """Test sending a key command via the `androidtv.adb_command` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    command = "HOME"
    response = None

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_shell", return_value=response
        ) as patch_shell:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADB_COMMAND,
                {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: command},
                blocking=True,
            )

            patch_shell.assert_called_with(f"input keyevent {KEYS[command]}")
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.attributes["adb_response"] is None


async def test_adb_command_get_properties(hass):
    """Test sending the "GET_PROPERTIES" command via the `androidtv.adb_command` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    command = "GET_PROPERTIES"
    response = {"test key": "test value"}

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.androidtv.androidtv_async.AndroidTVAsync.get_properties_dict",
            return_value=response,
        ) as patch_get_props:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADB_COMMAND,
                {ATTR_ENTITY_ID: entity_id, ATTR_COMMAND: command},
                blocking=True,
            )

            patch_get_props.assert_called()
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.attributes["adb_response"] == str(response)


async def test_learn_sendevent(hass):
    """Test the `androidtv.learn_sendevent` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    response = "sendevent 1 2 3 4"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.learn_sendevent",
            return_value=response,
        ) as patch_learn_sendevent:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_LEARN_SENDEVENT,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

            patch_learn_sendevent.assert_called()
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.attributes["adb_response"] == response


async def test_update_lock_not_acquired(hass):
    """Test that the state does not get updated when a `LockNotAcquiredException` is raised."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with patch(
        "androidtv.androidtv.androidtv_async.AndroidTVAsync.update",
        side_effect=LockNotAcquiredException,
    ), patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key]:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key]:
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_STANDBY


async def test_download(hass):
    """Test the `androidtv.download` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    device_path = "device/path"
    local_path = "local/path"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Failed download because path is not whitelisted
        with patch("androidtv.basetv.basetv_async.BaseTVAsync.adb_pull") as patch_pull:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DOWNLOAD,
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_DEVICE_PATH: device_path,
                    ATTR_LOCAL_PATH: local_path,
                },
                blocking=True,
            )
            patch_pull.assert_not_called()

        # Successful download
        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_pull"
        ) as patch_pull, patch.object(
            hass.config, "is_allowed_path", return_value=True
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DOWNLOAD,
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_DEVICE_PATH: device_path,
                    ATTR_LOCAL_PATH: local_path,
                },
                blocking=True,
            )
            patch_pull.assert_called_with(local_path, device_path)


async def test_upload(hass):
    """Test the `androidtv.upload` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)
    device_path = "device/path"
    local_path = "local/path"

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        # Failed upload because path is not whitelisted
        with patch("androidtv.basetv.basetv_async.BaseTVAsync.adb_push") as patch_push:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPLOAD,
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_DEVICE_PATH: device_path,
                    ATTR_LOCAL_PATH: local_path,
                },
                blocking=True,
            )
            patch_push.assert_not_called()

        # Successful upload
        with patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_push"
        ) as patch_push, patch.object(
            hass.config, "is_allowed_path", return_value=True
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_UPLOAD,
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_DEVICE_PATH: device_path,
                    ATTR_LOCAL_PATH: local_path,
                },
                blocking=True,
            )
            patch_push.assert_called_with(local_path, device_path)


async def test_androidtv_volume_set(hass):
    """Test setting the volume for an Android TV device."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    with patch(
        "androidtv.basetv.basetv_async.BaseTVAsync.set_volume_level", return_value=0.5
    ) as patch_set_volume_level:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            blocking=True,
        )

        patch_set_volume_level.assert_called_with(0.5)


async def test_get_image(hass, hass_ws_client):
    """Test taking a screen capture.

    This is based on `test_get_image` in tests/components/media_player/test_init.py.
    """
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    with patchers.patch_shell("11")[patch_key]:
        await hass.helpers.entity_component.async_update_entity(entity_id)

    client = await hass_ws_client(hass)

    with patch(
        "androidtv.basetv.basetv_async.BaseTVAsync.adb_screencap", return_value=b"image"
    ):
        await client.send_json(
            {"id": 5, "type": "media_player_thumbnail", "entity_id": entity_id}
        )

        msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["content_type"] == "image/png"
    assert msg["result"]["content"] == base64.b64encode(b"image").decode("utf-8")

    with patch(
        "androidtv.basetv.basetv_async.BaseTVAsync.adb_screencap",
        side_effect=RuntimeError,
    ):
        await client.send_json(
            {"id": 6, "type": "media_player_thumbnail", "entity_id": entity_id}
        )

        msg = await client.receive_json()

        # The device is unavailable, but getting the media image did not cause an exception
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def _test_service(
    hass,
    entity_id,
    ha_service_name,
    androidtv_method,
    additional_service_data=None,
    return_value=None,
):
    """Test generic Android TV media player entity service."""
    service_data = {ATTR_ENTITY_ID: entity_id}
    if additional_service_data:
        service_data.update(additional_service_data)

    androidtv_patch = (
        "androidtv.androidtv_async.AndroidTVAsync"
        if "android" in entity_id
        else "firetv.firetv_async.FireTVAsync"
    )
    with patch(
        f"androidtv.{androidtv_patch}.{androidtv_method}", return_value=return_value
    ) as service_call:
        await hass.services.async_call(
            MP_DOMAIN,
            ha_service_name,
            service_data=service_data,
            blocking=True,
        )
        assert service_call.called


async def test_services_androidtv(hass):
    """Test media player services for an Android TV device."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            with patchers.PATCH_DEVICE_PROPERTIES:
                assert await hass.config_entries.async_setup(config_entry.entry_id)
                await hass.async_block_till_done()

        with patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key]:
            await _test_service(
                hass, entity_id, SERVICE_MEDIA_NEXT_TRACK, "media_next_track"
            )
            await _test_service(hass, entity_id, SERVICE_MEDIA_PAUSE, "media_pause")
            await _test_service(hass, entity_id, SERVICE_MEDIA_PLAY, "media_play")
            await _test_service(
                hass, entity_id, SERVICE_MEDIA_PLAY_PAUSE, "media_play_pause"
            )
            await _test_service(
                hass, entity_id, SERVICE_MEDIA_PREVIOUS_TRACK, "media_previous_track"
            )
            await _test_service(hass, entity_id, SERVICE_MEDIA_STOP, "media_stop")
            await _test_service(hass, entity_id, SERVICE_TURN_OFF, "turn_off")
            await _test_service(hass, entity_id, SERVICE_TURN_ON, "turn_on")
            await _test_service(
                hass, entity_id, SERVICE_VOLUME_DOWN, "volume_down", return_value=0.1
            )
            await _test_service(
                hass,
                entity_id,
                SERVICE_VOLUME_SET,
                "set_volume_level",
                {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
                0.5,
            )
            await _test_service(
                hass, entity_id, SERVICE_VOLUME_UP, "volume_up", return_value=0.2
            )


async def test_services_firetv(hass):
    """Test media player services for a Fire TV device."""
    config = copy.deepcopy(CONFIG_FIRETV_ADB_SERVER)
    config[DOMAIN][CONF_OPTIONS] = {
        CONF_TURN_OFF_COMMAND: "test off",
        CONF_TURN_ON_COMMAND: "test on",
    }
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            with patchers.PATCH_DEVICE_PROPERTIES:
                assert await hass.config_entries.async_setup(config_entry.entry_id)
                await hass.async_block_till_done()

        with patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key]:
            await _test_service(hass, entity_id, SERVICE_MEDIA_STOP, "back")
            await _test_service(hass, entity_id, SERVICE_TURN_OFF, "adb_shell")
            await _test_service(hass, entity_id, SERVICE_TURN_ON, "adb_shell")


async def test_volume_mute(hass):
    """Test the volume mute service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            with patchers.PATCH_DEVICE_PROPERTIES:
                assert await hass.config_entries.async_setup(config_entry.entry_id)
                await hass.async_block_till_done()

        with patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key]:
            service_data = {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_MUTED: True}
            with patch(
                "androidtv.androidtv.androidtv_async.AndroidTVAsync.mute_volume",
                return_value=None,
            ) as mute_volume:
                # Don't send the mute key if the volume is already muted
                with patch(
                    "androidtv.androidtv.androidtv_async.AndroidTVAsync.is_volume_muted",
                    return_value=True,
                ):
                    await hass.services.async_call(
                        MP_DOMAIN,
                        SERVICE_VOLUME_MUTE,
                        service_data=service_data,
                        blocking=True,
                    )
                    assert not mute_volume.called

                # Send the mute key because the volume is not already muted
                with patch(
                    "androidtv.androidtv.androidtv_async.AndroidTVAsync.is_volume_muted",
                    return_value=False,
                ):
                    await hass.services.async_call(
                        MP_DOMAIN,
                        SERVICE_VOLUME_MUTE,
                        service_data=service_data,
                        blocking=True,
                    )
                    assert mute_volume.called


async def test_connection_closed_on_ha_stop(hass):
    """Test that the ADB socket connection is closed when HA stops."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_ADB_SERVER)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with patch(
            "androidtv.androidtv.androidtv_async.AndroidTVAsync.adb_close"
        ) as adb_close:
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            assert adb_close.called


async def test_exception(hass):
    """Test that the ADB connection gets closed when there is an unforeseen exception.

    HA will attempt to reconnect on the next update.
    """
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROIDTV_PYTHON_ADB)
    config_entry.add_to_hass(hass)

    with patchers.PATCH_ADB_DEVICE_TCP, patchers.patch_connect(True)[
        patch_key
    ], patchers.patch_shell(SHELL_RESPONSE_OFF)[
        patch_key
    ], patchers.PATCH_KEYGEN, patchers.PATCH_ANDROIDTV_OPEN, patchers.PATCH_SIGNER:
        with patchers.PATCH_DEVICE_PROPERTIES:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

        # When an unforeseen exception occurs, we close the ADB connection and raise the exception
        with patchers.PATCH_ANDROIDTV_UPDATE_EXCEPTION, pytest.raises(Exception):
            await hass.helpers.entity_component.async_update_entity(entity_id)
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

        # On the next update, HA will reconnect to the device
        await hass.helpers.entity_component.async_update_entity(entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF
