"""The tests for the androidtv platform."""

from datetime import timedelta
import logging
from typing import Any
from unittest.mock import patch

from adb_shell.exceptions import TcpTimeoutException as AdbShellTimeoutException
from androidtv.constants import APPS as ANDROIDTV_APPS, KEYS
from androidtv.exceptions import LockNotAcquiredException
import pytest

from homeassistant.components.androidtv.const import (
    CONF_APPS,
    CONF_EXCLUDE_UNNAMED_APPS,
    CONF_SCREENCAP,
    CONF_STATE_DETECTION_RULES,
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
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_PLAYING,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from . import patchers
from .common import (
    CONFIG_ANDROID_ADB_SERVER,
    CONFIG_ANDROID_DEFAULT,
    CONFIG_ANDROID_PYTHON_ADB,
    CONFIG_ANDROID_PYTHON_ADB_KEY,
    CONFIG_ANDROID_PYTHON_ADB_YAML,
    CONFIG_FIRETV_ADB_SERVER,
    CONFIG_FIRETV_DEFAULT,
    CONFIG_FIRETV_PYTHON_ADB,
    SHELL_RESPONSE_OFF,
    SHELL_RESPONSE_STANDBY,
    TEST_ENTITY_NAME,
    TEST_HOST_NAME,
    setup_mock_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.typing import ClientSessionGenerator

MSG_RECONNECT = {
    patchers.KEY_PYTHON: (
        f"ADB connection to {TEST_HOST_NAME}:{DEFAULT_PORT} successfully established"
    ),
    patchers.KEY_SERVER: (
        f"ADB connection to {TEST_HOST_NAME}:{DEFAULT_PORT} via ADB server"
        f" {patchers.ADB_SERVER_HOST}:{DEFAULT_ADB_SERVER_PORT} successfully"
        " established"
    ),
}


def _setup(config: dict[str, Any]) -> tuple[str, str, MockConfigEntry]:
    """Prepare mock entry for the media player tests."""
    return setup_mock_entry(config, MP_DOMAIN)


@pytest.mark.parametrize(
    "config",
    [
        CONFIG_ANDROID_PYTHON_ADB,
        CONFIG_ANDROID_PYTHON_ADB_YAML,
        CONFIG_FIRETV_PYTHON_ADB,
        CONFIG_ANDROID_ADB_SERVER,
        CONFIG_FIRETV_ADB_SERVER,
    ],
)
async def test_reconnect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, config: dict[str, Any]
) -> None:
    """Test that the error and reconnection attempts are logged correctly.

    "Handles device/service unavailable. Log a warning once when
    unavailable, log once when reconnected."

    https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
    """
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    caplog.clear()
    caplog.set_level(logging.WARNING)

    with (
        patchers.patch_connect(False)[patch_key],
        patchers.patch_shell(error=True)[patch_key],
    ):
        for _ in range(5):
            await async_update_entity(hass, entity_id)
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

    assert len(caplog.record_tuples) == 2
    assert caplog.record_tuples[0][1] == logging.ERROR
    assert caplog.record_tuples[1][1] == logging.WARNING

    caplog.set_level(logging.DEBUG)
    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
        patchers.PATCH_SCREENCAP,
    ):
        await async_update_entity(hass, entity_id)

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_STANDBY
        assert MSG_RECONNECT[patch_key] in caplog.record_tuples[2]


@pytest.mark.parametrize(
    "config",
    [
        CONFIG_ANDROID_PYTHON_ADB,
        CONFIG_FIRETV_PYTHON_ADB,
        CONFIG_ANDROID_ADB_SERVER,
        CONFIG_FIRETV_ADB_SERVER,
    ],
)
async def test_adb_shell_returns_none(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test the case that the ADB shell command returns `None`.

    The state should be `None` and the device should be unavailable.
    """
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE

    with (
        patchers.patch_shell(None)[patch_key],
        patchers.patch_shell(error=True)[patch_key],
    ):
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def test_setup_with_adbkey(hass: HomeAssistant) -> None:
    """Test that setup succeeds when using an ADB key."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_PYTHON_ADB_KEY)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
        patchers.PATCH_ISFILE,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "config",
    [
        CONFIG_ANDROID_DEFAULT,
        CONFIG_FIRETV_DEFAULT,
    ],
)
async def test_sources(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Test that sources (i.e., apps) are handled correctly for Android and Fire TV devices."""
    conf_apps = {
        "com.app.test1": "TEST 1",
        "com.app.test3": None,
        "com.app.test4": SHELL_RESPONSE_OFF,
    }
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_APPS: conf_apps})

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    patch_update = patchers.patch_androidtv_update(
        "playing",
        "com.app.test1",
        ["com.app.test1", "com.app.test2", "com.app.test3", "com.app.test4"],
        "hdmi",
        False,
        1,
        "HW5",
    )

    with patch_update[config[DOMAIN][CONF_DEVICE_CLASS]]:
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "TEST 1"
        assert sorted(state.attributes["source_list"]) == ["TEST 1", "com.app.test2"]

    patch_update = patchers.patch_androidtv_update(
        "playing",
        "com.app.test2",
        ["com.app.test2", "com.app.test1", "com.app.test3", "com.app.test4"],
        "hdmi",
        True,
        0,
        "HW5",
    )

    with patch_update[config[DOMAIN][CONF_DEVICE_CLASS]]:
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "com.app.test2"
        assert sorted(state.attributes["source_list"]) == ["TEST 1", "com.app.test2"]


@pytest.mark.parametrize(
    ("config", "expected_sources"),
    [
        (CONFIG_ANDROID_DEFAULT, ["TEST 1"]),
        (CONFIG_FIRETV_DEFAULT, ["TEST 1"]),
    ],
)
async def test_exclude_sources(
    hass: HomeAssistant, config: dict[str, Any], expected_sources: list[str]
) -> None:
    """Test that sources (i.e., apps) are handled correctly when the `exclude_unnamed_apps` config parameter is provided."""
    conf_apps = {
        "com.app.test1": "TEST 1",
        "com.app.test3": None,
        "com.app.test4": SHELL_RESPONSE_OFF,
    }
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_EXCLUDE_UNNAMED_APPS: True, CONF_APPS: conf_apps}
    )

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

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

    with patch_update[config[DOMAIN][CONF_DEVICE_CLASS]]:
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_PLAYING
        assert state.attributes["source"] == "TEST 1"
        assert sorted(state.attributes["source_list"]) == expected_sources


async def _test_select_source(
    hass: HomeAssistant, config, conf_apps, source, expected_arg, method_patch
) -> None:
    """Test that the methods for launching and stopping apps are called correctly when selecting a source."""
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_APPS: conf_apps})

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with method_patch as method_patch_used:
        await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: entity_id, ATTR_INPUT_SOURCE: source},
            blocking=True,
        )
        method_patch_used.assert_called_with(expected_arg)


@pytest.mark.parametrize(
    ("source", "expected_arg", "method_patch"),
    [
        ("com.app.test1", "com.app.test1", patchers.PATCH_LAUNCH_APP),
        ("TEST 1", "com.app.test1", patchers.PATCH_LAUNCH_APP),
        ("com.app.test2", "com.app.test2", patchers.PATCH_LAUNCH_APP),
        ("com.app.test3", "com.app.test3", patchers.PATCH_LAUNCH_APP),
        ("!com.app.test1", "com.app.test1", patchers.PATCH_STOP_APP),
        ("!TEST 1", "com.app.test1", patchers.PATCH_STOP_APP),
        ("!com.app.test2", "com.app.test2", patchers.PATCH_STOP_APP),
        ("!com.app.test3", "com.app.test3", patchers.PATCH_STOP_APP),
    ],
)
async def test_select_source_androidtv(
    hass: HomeAssistant, source, expected_arg, method_patch
) -> None:
    """Test that an app can be launched for AndroidTV."""
    conf_apps = {
        "com.app.test1": "TEST 1",
        "com.app.test3": None,
    }
    await _test_select_source(
        hass, CONFIG_ANDROID_DEFAULT, conf_apps, source, expected_arg, method_patch
    )


async def test_androidtv_select_source_overridden_app_name(hass: HomeAssistant) -> None:
    """Test that when an app name is overridden via the `apps` configuration parameter, the app is launched correctly."""
    # Evidence that the default YouTube app ID will be overridden
    conf_apps = {
        "com.youtube.test": "YouTube",
    }
    assert "YouTube" in ANDROIDTV_APPS.values()
    assert "com.youtube.test" not in ANDROIDTV_APPS
    await _test_select_source(
        hass,
        CONFIG_ANDROID_PYTHON_ADB,
        conf_apps,
        "YouTube",
        "com.youtube.test",
        patchers.PATCH_LAUNCH_APP,
    )


@pytest.mark.parametrize(
    ("source", "expected_arg", "method_patch"),
    [
        ("com.app.test1", "com.app.test1", patchers.PATCH_LAUNCH_APP),
        ("TEST 1", "com.app.test1", patchers.PATCH_LAUNCH_APP),
        ("com.app.test2", "com.app.test2", patchers.PATCH_LAUNCH_APP),
        ("com.app.test3", "com.app.test3", patchers.PATCH_LAUNCH_APP),
        ("!com.app.test1", "com.app.test1", patchers.PATCH_STOP_APP),
        ("!TEST 1", "com.app.test1", patchers.PATCH_STOP_APP),
        ("!com.app.test2", "com.app.test2", patchers.PATCH_STOP_APP),
        ("!com.app.test3", "com.app.test3", patchers.PATCH_STOP_APP),
    ],
)
async def test_select_source_firetv(
    hass: HomeAssistant, source, expected_arg, method_patch
) -> None:
    """Test that an app can be launched for FireTV."""
    conf_apps = {
        "com.app.test1": "TEST 1",
        "com.app.test3": None,
    }
    await _test_select_source(
        hass, CONFIG_FIRETV_DEFAULT, conf_apps, source, expected_arg, method_patch
    )


@pytest.mark.parametrize(
    ("config", "connect"),
    [
        (CONFIG_ANDROID_DEFAULT, False),
        (CONFIG_FIRETV_DEFAULT, False),
        (CONFIG_ANDROID_DEFAULT, True),
        (CONFIG_FIRETV_DEFAULT, True),
    ],
)
async def test_setup_fail(
    hass: HomeAssistant, config: dict[str, Any], connect: bool
) -> None:
    """Test that the entity is not created when the ADB connection is not established."""
    patch_key, entity_id, config_entry = _setup(config)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(connect)[patch_key],
        patchers.patch_shell(
            SHELL_RESPONSE_OFF, error=True, exc=AdbShellTimeoutException
        )[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert state is None


async def test_adb_command(hass: HomeAssistant) -> None:
    """Test sending a command via the `androidtv.adb_command` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    command = "test command"
    response = "test response"

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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


async def test_adb_command_unicode_decode_error(hass: HomeAssistant) -> None:
    """Test sending a command via the `androidtv.adb_command` service that raises a UnicodeDecodeError exception."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    command = "test command"
    response = b"test response"

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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


async def test_adb_command_key(hass: HomeAssistant) -> None:
    """Test sending a key command via the `androidtv.adb_command` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    command = "HOME"
    response = None

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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


async def test_adb_command_get_properties(hass: HomeAssistant) -> None:
    """Test sending the "GET_PROPERTIES" command via the `androidtv.adb_command` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    command = "GET_PROPERTIES"
    response = {"test key": "test value"}

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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


async def test_learn_sendevent(hass: HomeAssistant) -> None:
    """Test the `androidtv.learn_sendevent` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    response = "sendevent 1 2 3 4"

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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


async def test_update_lock_not_acquired(hass: HomeAssistant) -> None:
    """Test that the state does not get updated when a `LockNotAcquiredException` is raised."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with (
        patch(
            "androidtv.androidtv.androidtv_async.AndroidTVAsync.update",
            side_effect=LockNotAcquiredException,
        ),
        patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
    ):
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

    with (
        patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
        patchers.PATCH_SCREENCAP,
    ):
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_STANDBY


async def test_download(hass: HomeAssistant) -> None:
    """Test the `androidtv.download` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    device_path = "device/path"
    local_path = "local/path"

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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
        with (
            patch("androidtv.basetv.basetv_async.BaseTVAsync.adb_pull") as patch_pull,
            patch.object(hass.config, "is_allowed_path", return_value=True),
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


async def test_upload(hass: HomeAssistant) -> None:
    """Test the `androidtv.upload` service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    device_path = "device/path"
    local_path = "local/path"

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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
        with (
            patch("androidtv.basetv.basetv_async.BaseTVAsync.adb_push") as patch_push,
            patch.object(hass.config, "is_allowed_path", return_value=True),
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


async def test_androidtv_volume_set(hass: HomeAssistant) -> None:
    """Test setting the volume for an Android device."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
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


async def test_get_image_http(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test taking a screen capture.

    This is based on `test_get_image_http` in tests/components/media_player/test_init.py.
    """
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with (
        patchers.patch_shell("11")[patch_key],
        patchers.PATCH_SCREENCAP as patch_screen_cap,
    ):
        await async_update_entity(hass, entity_id)
        patch_screen_cap.assert_called()

    media_player_name = "media_player." + slugify(
        CONFIG_ANDROID_DEFAULT[TEST_ENTITY_NAME]
    )
    state = hass.states.get(media_player_name)
    assert "entity_picture_local" not in state.attributes

    client = await hass_client_no_auth()

    resp = await client.get(state.attributes["entity_picture"])
    content = await resp.read()
    assert content == b"image"

    next_update = utcnow() + timedelta(seconds=30)
    with (
        patchers.patch_shell("11")[patch_key],
        patchers.PATCH_SCREENCAP as patch_screen_cap,
        patch("homeassistant.util.utcnow", return_value=next_update),
    ):
        async_fire_time_changed(hass, next_update, True)
        await hass.async_block_till_done()
        patch_screen_cap.assert_not_called()

    next_update = utcnow() + timedelta(seconds=60)
    with (
        patchers.patch_shell("11")[patch_key],
        patchers.PATCH_SCREENCAP as patch_screen_cap,
        patch("homeassistant.util.utcnow", return_value=next_update),
    ):
        async_fire_time_changed(hass, next_update, True)
        await hass.async_block_till_done()
        patch_screen_cap.assert_called()


async def test_get_image_http_fail(hass: HomeAssistant) -> None:
    """Test taking a screen capture fail."""

    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with (
        patchers.patch_shell("11")[patch_key],
        patch(
            "androidtv.basetv.basetv_async.BaseTVAsync.adb_screencap",
            side_effect=ConnectionResetError,
        ),
    ):
        await async_update_entity(hass, entity_id)

    # The device is unavailable, but getting the media image did not cause an exception
    media_player_name = "media_player." + slugify(
        CONFIG_ANDROID_DEFAULT[TEST_ENTITY_NAME]
    )
    state = hass.states.get(media_player_name)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_get_image_disabled(hass: HomeAssistant) -> None:
    """Test that the screencap option can disable entity_picture."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_SCREENCAP: False}
    )

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with patchers.patch_shell("11")[patch_key]:
        await async_update_entity(hass, entity_id)

    media_player_name = "media_player." + slugify(
        CONFIG_ANDROID_DEFAULT[TEST_ENTITY_NAME]
    )
    state = hass.states.get(media_player_name)
    assert "entity_picture_local" not in state.attributes
    assert "entity_picture" not in state.attributes


async def _test_service(
    hass: HomeAssistant,
    entity_id,
    ha_service_name,
    androidtv_method,
    additional_service_data=None,
    return_value=None,
) -> None:
    """Test generic Android media player entity service."""
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


async def test_services_androidtv(hass: HomeAssistant) -> None:
    """Test media player services for an Android device."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with (
            patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
            patchers.PATCH_SCREENCAP,
        ):
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


async def test_services_firetv(hass: HomeAssistant) -> None:
    """Test media player services for a Fire TV device."""
    patch_key, entity_id, config_entry = _setup(CONFIG_FIRETV_DEFAULT)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_TURN_OFF_COMMAND: "test off",
            CONF_TURN_ON_COMMAND: "test on",
        },
    )

    with patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with (
            patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
            patchers.PATCH_SCREENCAP,
        ):
            await _test_service(hass, entity_id, SERVICE_MEDIA_STOP, "back")
            await _test_service(hass, entity_id, SERVICE_TURN_OFF, "adb_shell")
            await _test_service(hass, entity_id, SERVICE_TURN_ON, "adb_shell")


async def test_volume_mute(hass: HomeAssistant) -> None:
    """Test the volume mute service."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with patchers.patch_connect(True)[patch_key]:
        with patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key]:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

        with (
            patchers.patch_shell(SHELL_RESPONSE_STANDBY)[patch_key],
            patchers.PATCH_SCREENCAP,
        ):
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


async def test_connection_closed_on_ha_stop(hass: HomeAssistant) -> None:
    """Test that the ADB socket connection is closed when HA stops."""
    patch_key, _, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        with patch("androidtv.basetv.basetv_async.BaseTVAsync.adb_close") as adb_close:
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            assert adb_close.called


async def test_exception(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test that the ADB connection gets closed when there is an unforeseen exception.

    HA will attempt to reconnect on the next update.
    """
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

        caplog.clear()
        caplog.set_level(logging.ERROR)

        # When an unforeseen exception occurs, we close the ADB connection and raise the exception
        with patchers.PATCH_ANDROIDTV_UPDATE_EXCEPTION:
            await async_update_entity(hass, entity_id)

        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
        assert len(caplog.record_tuples) == 1
        assert caplog.record_tuples[0][1] == logging.ERROR
        assert caplog.record_tuples[0][2].startswith(
            "Unexpected exception executing an ADB command"
        )

        # On the next update, HA will reconnect to the device
        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF


async def test_options_reload(hass: HomeAssistant) -> None:
    """Test changing an option that will cause integration reload."""
    patch_key, entity_id, config_entry = _setup(CONFIG_ANDROID_DEFAULT)
    config_entry.add_to_hass(hass)

    with (
        patchers.patch_connect(True)[patch_key],
        patchers.patch_shell(SHELL_RESPONSE_OFF)[patch_key],
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        await async_update_entity(hass, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_OFF

        with patchers.PATCH_SETUP_ENTRY as setup_entry_call:
            # change an option that not require integration reload
            hass.config_entries.async_update_entry(
                config_entry, options={CONF_SCREENCAP: False}
            )
            await hass.async_block_till_done()

            assert not setup_entry_call.called

            # change an option that require integration reload
            hass.config_entries.async_update_entry(
                config_entry, options={CONF_STATE_DETECTION_RULES: {}}
            )
            await hass.async_block_till_done()

            assert setup_entry_call.called
            assert config_entry.state is ConfigEntryState.LOADED
