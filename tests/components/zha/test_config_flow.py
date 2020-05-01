"""Tests for ZHA config flow."""

from unittest import mock

import serial.tools.list_ports
import zigpy.config

from homeassistant.components.zha import config_flow
from homeassistant.components.zha.core.const import CONF_RADIO_TYPE, CONTROLLER, DOMAIN

import tests.async_mock
from tests.common import MockConfigEntry


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo()
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1"
    port.description = "Some serial port"

    return port


@mock.patch(
    "serial.tools.list_ports.comports", mock.MagicMock(return_value=[com_port()])
)
async def test_user_flow(hass):
    """Test user flow."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    port = com_port()
    port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

    with mock.patch.object(
        flow, "detect_radios", return_value=mock.sentinel.data,
    ):
        result = await flow.async_step_user(
            user_input={zigpy.config.CONF_DEVICE_PATH: port_select}
        )
    assert result["type"] == "create_entry"
    assert result["title"].startswith(port.device)
    assert result["data"] is mock.sentinel.data

    with mock.patch.object(
        flow, "detect_radios", return_value=None,
    ):
        result = await flow.async_step_user(
            user_input={zigpy.config.CONF_DEVICE_PATH: port_select}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pick_radio"

    await flow.async_step_user()


async def test_user_flow_manual(hass):
    """Test user flow manual entry."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(
        user_input={zigpy.config.CONF_DEVICE_PATH: config_flow.CONF_MANUAL_PATH}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pick_radio"


async def test_pick_radio_flow(hass):
    """Test radio picker."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_pick_radio({CONF_RADIO_TYPE: "ezsp"})
    assert result["type"] == "form"
    assert result["step_id"] == "port_config"

    await flow.async_step_pick_radio()


async def test_user_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, data={"usb_path": "/dev/ttyUSB1"}).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == "abort"


async def test_probe_radios(hass):
    """Test detect radios."""
    app_ctrl_cls = mock.MagicMock()
    app_ctrl_cls.SCHEMA_DEVICE = zigpy.config.SCHEMA_DEVICE
    app_ctrl_cls.probe = tests.async_mock.AsyncMock(side_effect=(True, False))

    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    with mock.patch.dict(config_flow.RADIO_TYPES, {"ezsp": {CONTROLLER: app_ctrl_cls}}):
        res = await flow.detect_radios("/dev/null")
        assert app_ctrl_cls.probe.await_count == 1
        assert res[CONF_RADIO_TYPE] == "ezsp"
        assert zigpy.config.CONF_DEVICE in res
        assert (
            res[zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH] == "/dev/null"
        )

        res = await flow.detect_radios("/dev/null")
        assert res is None


async def test_user_port_config_fail(hass):
    """Test port config flow."""
    app_ctrl_cls = mock.MagicMock()
    app_ctrl_cls.SCHEMA_DEVICE = zigpy.config.SCHEMA_DEVICE
    app_ctrl_cls.probe = tests.async_mock.AsyncMock(side_effect=(False, True))

    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass
    await flow.async_step_pick_radio(user_input={CONF_RADIO_TYPE: "ezsp"})

    with mock.patch.dict(config_flow.RADIO_TYPES, {"ezsp": {CONTROLLER: app_ctrl_cls}}):
        result = await flow.async_step_port_config(
            {zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "port_config"
        assert result["errors"]["base"] == "cannot_connect"

        result = await flow.async_step_port_config(
            {zigpy.config.CONF_DEVICE_PATH: "/dev/ttyUSB33"}
        )
        assert result["type"] == "create_entry"
        assert result["title"].startswith("/dev/ttyUSB33")
        assert (
            result["data"][zigpy.config.CONF_DEVICE][zigpy.config.CONF_DEVICE_PATH]
            == "/dev/ttyUSB33"
        )
        assert result["data"][CONF_RADIO_TYPE] == "ezsp"
