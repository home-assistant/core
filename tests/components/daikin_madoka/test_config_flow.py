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

from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"
DOMAIN = "daikin_madoka"


class _BLEDevice:
    def __init__(self, address):

        self.address = address


TEST_DEVICES = "aa:bb:cc:dd:ee:ff, 00:11:22:33:44:55"
TEST_DISCOVERED_DEVICES = [
    _BLEDevice("aa:bb:cc:dd:ee:ff"),
    _BLEDevice("00:11:22:33:44:55"),
]
FAIL_TEST_DEVICES = "XX:XX:XX:XX:XX:XX, error_string"
TEST_DEVICE = "hci0"
TEST_SCAN_INTERVAL = 15
TEST_FORCE_UPDATE = False


async def test_form(hass):
    """Test we can setup though the user path."""

    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):

        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == config_entries.SOURCE_USER
        assert result["errors"] == {}

        with patch("bleak.subprocess.Popen", return_value="BluetoothCtl: 5.53",), patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.FlowHandler.is_valid_adapter",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup", return_value=True
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup_entry",
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
            await hass.async_block_till_done()

            assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
            assert result2["title"] == "BRC1H"
            assert result2["data"] == {
                CONF_DEVICES: list(map(lambda x: x.strip(), TEST_DEVICES.split(","))),
                CONF_DEVICE: TEST_DEVICE,
                CONF_DISCOVERY: False,  # This is only used during the configuration, no need to store it
                CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
                CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
            }


async def test_import(hass):
    """Test we can import."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        await setup.async_setup_component(hass, "persistent_notification", {})
        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.FlowHandler.is_valid_adapter",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup", return_value=True
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup_entry",
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
        assert result["title"] == "BRC1H"
        assert result["data"] == {
            CONF_DEVICES: list(map(lambda x: x.strip(), TEST_DEVICES.split(","))),
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
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.FlowHandler.is_valid_adapter",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup", return_value=True
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup_entry",
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

        assert result2["type"] == "form"
        assert result2["errors"] == {CONF_DEVICES: "not_a_mac"}


async def test_form_invalid_connect_devices(hass):
    """Test we handle invalid devices."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=[],
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.FlowHandler.is_valid_adapter",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup", return_value=True
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup_entry",
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

        assert result2["type"] == "form"
        assert result2["errors"] == {CONF_DEVICES: "device_not_found"}


async def test_form_invalid_connect_adapter(hass):
    """Test we handle cannot connect error."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["errors"] == {}

        with patch(
            "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
            return_value=True,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.discover_devices",
            return_value=TEST_DISCOVERED_DEVICES,
        ), patch(
            "homeassistant.components.daikin_madoka.config_flow.FlowHandler.is_valid_adapter",
            return_value=False,
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup", return_value=True
        ), patch(
            "homeassistant.components.daikin_madoka.async_setup_entry",
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

        assert result2["type"] == "form"
        assert result2["errors"] == {CONF_DEVICE: "cannot_connect"}


async def test_abort_if_already_setup(hass):
    """Test we abort if Daikin is already setup."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        MockConfigEntry(domain=DOMAIN, unique_id="BRC1H-id").add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
