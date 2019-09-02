"""The tests for the androidtv platform."""
import logging
import unittest

from homeassistant.setup import async_setup_component
from homeassistant.components.androidtv.media_player import (
    AndroidTVDevice,
    ANDROIDTV_DOMAIN,
    CONF_ADB_SERVER_IP,
    FireTVDevice,
    setup as androidtv_setup,
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


ENTITY_ID_ANDROID_TV = "media_player.android_tv"
ENTITY_ID_FIRE_TV = "media_player.fire_tv"

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

    assert (
        "ADB connection to 127.0.0.1:5555 successfully established"
        in caplog.record_tuples[2]
    )

    return True


async def test_reconnect_androidtv_python_adb(hass, caplog):
    """Test that the error and reconnection attempts are logged correctly.

    "Handles device/service unavailable. Log a warning once when
    unavailable, log once when reconnected."

    https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
    """
    assert await _test_reconnect(
        hass,
        caplog,
        CONFIG_ANDROIDTV_PYTHON_ADB,
        ENTITY_ID_ANDROID_TV,
        patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS,
        patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS,
        patchers.PATCH_PYTHON_ADB_CONNECT_FAIL,
        patchers.PATCH_PYTHON_ADB_COMMAND_FAIL,
    )
    """with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
        assert await async_setup_component(hass, DOMAIN, CONFIG_ANDROIDTV_PYTHON_ADB)

    caplog.clear()
    caplog.set_level(logging.WARNING)

    with patchers.PATCH_PYTHON_ADB_CONNECT_FAIL, patchers.PATCH_PYTHON_ADB_COMMAND_FAIL:
        for _ in range(5):
            await hass.helpers.entity_component.async_update_entity(ENTITY_ID_ANDROID_TV)
            state = hass.states.get(ENTITY_ID_ANDROID_TV)
            assert state.state == STATE_UNAVAILABLE
            # assert not state.attributes["available"]

    assert len(caplog.record_tuples) == 2

    caplog.set_level(logging.DEBUG)
    with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
        # Update 1 will reconnect
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID_ANDROID_TV)
        # state = hass.states.get(entity_id)
        assert hass.states.get(ENTITY_ID_ANDROID_TV).state != STATE_UNAVAILABLE

        # Update 2 will update the state
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID_ANDROID_TV)
        state = hass.states.get(ENTITY_ID_ANDROID_TV)
        assert state.state != STATE_UNAVAILABLE
        # assert state.attributes["available"]

    assert "ADB connection to 127.0.0.1:5555 successfully established" in caplog.record_tuples[2]"""


async def test_adb_shell_returns_none_androidtv_python_adb(hass):
    """Test the case that the ADB shell command returns `None`.

    The state should be `None` and the device should be unavailable.
    """
    with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
        assert await async_setup_component(hass, DOMAIN, CONFIG_ANDROIDTV_PYTHON_ADB)
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID_ANDROID_TV)
        assert hass.states.get(ENTITY_ID_ANDROID_TV).state != STATE_UNAVAILABLE

    with patchers.PATCH_PYTHON_ADB_COMMAND_NONE:
        await hass.helpers.entity_component.async_update_entity(ENTITY_ID_ANDROID_TV)
        assert hass.states.get(ENTITY_ID_ANDROID_TV).state == STATE_UNAVAILABLE


class TestAndroidTVPythonImplementation(unittest.TestCase):
    """Test the androidtv media player for an Android TV device."""

    def setUp(self):
        """Set up an `AndroidTVDevice` media player."""
        with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
            aftv = androidtv_setup("IP:PORT", device_class="androidtv")
            self.aftv = AndroidTVDevice(aftv, "Fake Android TV", {}, None, None)

    def test_reconnect(self):
        """Test that the error and reconnection attempts are logged correctly.

        "Handles device/service unavailable. Log a warning once when
        unavailable, log once when reconnected."

        https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
        """
        with self.assertLogs(level=logging.WARNING) as logs:
            with patchers.PATCH_PYTHON_ADB_CONNECT_FAIL, patchers.PATCH_PYTHON_ADB_COMMAND_FAIL:
                for _ in range(5):
                    self.aftv.update()
                    self.assertFalse(self.aftv.available)
                    self.assertIsNone(self.aftv.state)

        assert len(logs.output) == 2
        assert logs.output[0].startswith("ERROR")
        assert logs.output[1].startswith("WARNING")

        with self.assertLogs(level=logging.DEBUG) as logs:
            with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
                # Update 1 will reconnect
                self.aftv.update()
                self.assertTrue(self.aftv.available)

                # Update 2 will update the state
                self.aftv.update()
                self.assertTrue(self.aftv.available)
                self.assertIsNotNone(self.aftv.state)

        assert (
            "ADB connection to {} successfully established".format(self.aftv.aftv.host)
            in logs.output[0]
        )

    def test_adb_shell_returns_none(self):
        """Test the case that the ADB shell command returns `None`.

        The state should be `None` and the device should be unavailable.
        """
        with patchers.PATCH_PYTHON_ADB_COMMAND_NONE:
            self.aftv.update()
            self.assertFalse(self.aftv.available)
            self.assertIsNone(self.aftv.state)

        with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
            # Update 1 will reconnect
            self.aftv.update()
            self.assertTrue(self.aftv.available)

            # Update 2 will update the state
            self.aftv.update()
            self.assertTrue(self.aftv.available)
            self.assertIsNotNone(self.aftv.state)


class TestAndroidTVServerImplementation(unittest.TestCase):
    """Test the androidtv media player for an Android TV device."""

    def setUp(self):
        """Set up an `AndroidTVDevice` media player."""
        with patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS, patchers.PATCH_ADB_SERVER_AVAILABLE:
            aftv = androidtv_setup(
                "IP:PORT", adb_server_ip="ADB_SERVER_IP", device_class="androidtv"
            )
            self.aftv = AndroidTVDevice(aftv, "Fake Android TV", {}, None, None)

    def test_reconnect(self):
        """Test that the error and reconnection attempts are logged correctly.

        "Handles device/service unavailable. Log a warning once when
        unavailable, log once when reconnected."

        https://developers.home-assistant.io/docs/en/integration_quality_scale_index.html
        """
        with self.assertLogs(level=logging.WARNING) as logs:
            with patchers.PATCH_ADB_SERVER_CONNECT_FAIL, patchers.PATCH_ADB_SERVER_COMMAND_FAIL:
                for _ in range(5):
                    self.aftv.update()
                    self.assertFalse(self.aftv.available)
                    self.assertIsNone(self.aftv.state)

        assert len(logs.output) == 2
        assert logs.output[0].startswith("ERROR")
        assert logs.output[1].startswith("WARNING")

        with self.assertLogs(level=logging.DEBUG) as logs:
            with patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS:
                self.aftv.update()
                self.assertTrue(self.aftv.available)
                self.assertIsNotNone(self.aftv.state)

        assert (
            "ADB connection to {} via ADB server {}:{} successfully established".format(
                self.aftv.aftv.host,
                self.aftv.aftv.adb_server_ip,
                self.aftv.aftv.adb_server_port,
            )
            in logs.output[0]
        )

    def test_adb_shell_returns_none(self):
        """Test the case that the ADB shell command returns `None`.

        The state should be `None` and the device should be unavailable.
        """
        with patchers.PATCH_ADB_SERVER_COMMAND_NONE:
            self.aftv.update()
            self.assertFalse(self.aftv.available)
            self.assertIsNone(self.aftv.state)

        with patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS:
            self.aftv.update()
            self.assertTrue(self.aftv.available)
            self.assertIsNotNone(self.aftv.state)


class TestFireTVPythonImplementation(TestAndroidTVPythonImplementation):
    """Test the androidtv media player for a Fire TV device."""

    def setUp(self):
        """Set up a `FireTVDevice` media player."""
        with patchers.PATCH_PYTHON_ADB_CONNECT_SUCCESS, patchers.PATCH_PYTHON_ADB_COMMAND_SUCCESS:
            aftv = androidtv_setup("IP:PORT", device_class="firetv")
            self.aftv = FireTVDevice(aftv, "Fake Fire TV", {}, True, None, None)


class TestFireTVServerImplementation(TestAndroidTVServerImplementation):
    """Test the androidtv media player for a Fire TV device."""

    def setUp(self):
        """Set up a `FireTVDevice` media player."""
        with patchers.PATCH_ADB_SERVER_CONNECT_SUCCESS, patchers.PATCH_ADB_SERVER_AVAILABLE:
            aftv = androidtv_setup(
                "IP:PORT", adb_server_ip="ADB_SERVER_IP", device_class="firetv"
            )
            self.aftv = FireTVDevice(aftv, "Fake Fire TV", {}, True, None, None)
