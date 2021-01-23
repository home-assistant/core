"""Tests for the init file."""
import json
from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED

from tests.common import load_fixture
from tests.components.daikin_madoka import (
    DOMAIN,
    TEST_DISCOVERED_DEVICES,
    async_init_integration,
    create_controller_aborted,
    create_controller_mock,
)


async def test_async_setup_entry_connection_aborted(hass):
    """Test a successful setup entry."""

    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ):
        from homeassistant.components.daikin_madoka.const import CONTROLLERS

        fixture = json.loads(load_fixture("daikin_madoka/mode_auto_cooling.json"))
        entry = await async_init_integration(
            hass, create_controller_aborted(fixture, True, False)
        )
        assert type(hass.data[DOMAIN][entry.entry_id][CONTROLLERS]) is dict
        assert len(hass.data[DOMAIN][entry.entry_id][CONTROLLERS].values()) == len(
            TEST_DISCOVERED_DEVICES
        )


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""

    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ):
        from homeassistant.components.daikin_madoka.const import CONTROLLERS

        fixture = json.loads(load_fixture("daikin_madoka/mode_auto_cooling.json"))
        entry = await async_init_integration(hass, create_controller_mock(fixture))
        assert type(hass.data[DOMAIN][entry.entry_id][CONTROLLERS]) is dict
        assert len(hass.data[DOMAIN][entry.entry_id][CONTROLLERS].values()) == len(
            TEST_DISCOVERED_DEVICES
        )


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=[],
    ), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.Controller.start", return_value=True
    ):
        fixture = json.loads(load_fixture("daikin_madoka/mode_auto_cooling.json"))
        entry = await async_init_integration(hass, create_controller_mock(fixture))

        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ENTRY_STATE_LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state == ENTRY_STATE_NOT_LOADED
        assert not hass.data.get(DOMAIN)
