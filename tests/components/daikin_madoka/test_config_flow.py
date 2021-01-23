# pylint: disable=redefined-outer-name
"""Tests for the Daikin config flow."""
from unittest.mock import MagicMock, patch

from homeassistant import config_entries, setup
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_FORCE_UPDATE,
    CONF_SCAN_INTERVAL,
)
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    FAIL_TEST_DEVICES,
    TEST_DEVICE,
    TEST_DEVICES,
    TEST_DISCOVERED_DEVICES,
    TEST_FORCE_UPDATE,
    TEST_SCAN_INTERVAL,
    split_devices,
)

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we can setup though the user path."""

    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):

        from homeassistant.components.daikin_madoka.const import DOMAIN

        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == config_entries.SOURCE_USER
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.Controller.start",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_DEVICES: TEST_DEVICES,
                    CONF_DEVICE: TEST_DEVICE,
                    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                    CONF_DISCOVERY: True,
                    CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
                },
            )
            # await hass.async_block_till_done()
            from homeassistant.components.daikin_madoka.const import TITLE

            assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
            assert result2["title"] == TITLE
            assert result2["data"] == {
                CONF_DEVICES: split_devices(TEST_DEVICES),
                CONF_DEVICE: TEST_DEVICE,
                CONF_DISCOVERY: False,  # This is only used during the configuration, no need to store it
                CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
            }
            print("as")


async def test_import(hass):
    """Test we can import."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        from homeassistant.components.daikin_madoka.const import DOMAIN, TITLE

        await setup.async_setup_component(hass, "persistent_notification", {})
        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.Controller.start",
            return_value=True,
        ):

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_DEVICES: TEST_DEVICES,
                    CONF_DEVICE: TEST_DEVICE,
                    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                    CONF_DISCOVERY: True,
                    CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == TITLE
        assert result["data"] == {
            CONF_DEVICES: split_devices(TEST_DEVICES),
            CONF_DEVICE: TEST_DEVICE,
            CONF_DISCOVERY: False,  # This is only used during the configuration, no need to store it
            CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
            CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        }


async def test_form_wrong_format_devices(hass):
    """Test we handle invalid devices."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        from homeassistant.components.daikin_madoka.const import DOMAIN

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.Controller.start",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_DEVICES: FAIL_TEST_DEVICES,
                    CONF_DEVICE: TEST_DEVICE,
                    CONF_DISCOVERY: True,
                    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                    CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
                },
            )

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["errors"] == {CONF_DEVICES: "not_a_mac"}


async def test_form_invalid_connect_devices(hass):
    """Test we handle invalid devices."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        from homeassistant.components.daikin_madoka.const import DOMAIN

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=[],
        ), patch(
            "homeassistant.components.daikin_madoka.discover_devices",
            return_value=[],
        ), patch(
            "homeassistant.components.daikin_madoka.Controller.start",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_DEVICES: TEST_DEVICES,
                    CONF_DEVICE: TEST_DEVICE,
                    CONF_DISCOVERY: True,
                    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                    CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
                },
            )

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["errors"] == {CONF_DEVICES: "device_not_found"}


async def test_form_invalid_connect_adapter(hass):
    """Test we handle cannot connect error."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        from homeassistant.components.daikin_madoka.const import DOMAIN

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            side_effect=Exception("Device not present"),
        ), patch(
            "homeassistant.components.daikin_madoka.Controller.start",
            return_value=True,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_DEVICES: TEST_DEVICES,
                    CONF_DEVICE: TEST_DEVICE,
                    CONF_DISCOVERY: True,
                    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                    CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
                },
            )

        assert result2["type"] == RESULT_TYPE_FORM
        assert result2["errors"] == {CONF_DEVICE: "cannot_connect"}


async def test_abort_if_already_setup(hass):
    """Test we abort if Daikin is already setup."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        from homeassistant.components.daikin_madoka.const import DOMAIN, UNIQUE_ID

        MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID).add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
