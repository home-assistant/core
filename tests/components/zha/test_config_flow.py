"""Tests for ZHA config flow."""
from unittest import mock

from homeassistant.components.zha import config_flow
from homeassistant.components.zha.core.const import CONTROLLER, DOMAIN, ZHA_GW_RADIO
import homeassistant.components.zha.core.registries

import tests.async_mock
from tests.common import MockConfigEntry


async def test_user_flow(hass):
    """Test that config flow works."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    with tests.async_mock.patch(
        "homeassistant.components.zha.config_flow.check_zigpy_connection",
        return_value=False,
    ):
        result = await flow.async_step_user(
            user_input={"usb_path": "/dev/ttyUSB1", "radio_type": "ezsp"}
        )

    assert result["errors"] == {"base": "cannot_connect"}

    with tests.async_mock.patch(
        "homeassistant.components.zha.config_flow.check_zigpy_connection",
        return_value=True,
    ):
        result = await flow.async_step_user(
            user_input={"usb_path": "/dev/ttyUSB1", "radio_type": "ezsp"}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "/dev/ttyUSB1"
    assert result["data"] == {"usb_path": "/dev/ttyUSB1", "radio_type": "ezsp"}


async def test_user_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, data={"usb_path": "/dev/ttyUSB1"}).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == "abort"


async def test_import_flow(hass):
    """Test import from configuration.yaml ."""
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(
        {"usb_path": "/dev/ttyUSB1", "radio_type": "xbee"}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "/dev/ttyUSB1"
    assert result["data"] == {"usb_path": "/dev/ttyUSB1", "radio_type": "xbee"}


async def test_import_flow_existing_config_entry(hass):
    """Test import from configuration.yaml ."""
    MockConfigEntry(domain=DOMAIN, data={"usb_path": "/dev/ttyUSB1"}).add_to_hass(hass)
    flow = config_flow.ZhaFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(
        {"usb_path": "/dev/ttyUSB1", "radio_type": "xbee"}
    )

    assert result["type"] == "abort"


async def test_check_zigpy_connection():
    """Test config flow validator."""

    mock_radio = tests.async_mock.MagicMock()
    mock_radio.connect = tests.async_mock.AsyncMock()
    radio_cls = tests.async_mock.MagicMock(return_value=mock_radio)

    bad_radio = tests.async_mock.MagicMock()
    bad_radio.connect = tests.async_mock.AsyncMock(side_effect=Exception)
    bad_radio_cls = tests.async_mock.MagicMock(return_value=bad_radio)

    mock_ctrl = tests.async_mock.MagicMock()
    mock_ctrl.startup = tests.async_mock.AsyncMock()
    mock_ctrl.shutdown = tests.async_mock.AsyncMock()
    ctrl_cls = tests.async_mock.MagicMock(return_value=mock_ctrl)
    new_radios = {
        mock.sentinel.radio: {ZHA_GW_RADIO: radio_cls, CONTROLLER: ctrl_cls},
        mock.sentinel.bad_radio: {ZHA_GW_RADIO: bad_radio_cls, CONTROLLER: ctrl_cls},
    }

    with mock.patch.dict(
        homeassistant.components.zha.core.registries.RADIO_TYPES, new_radios, clear=True
    ):
        assert not await config_flow.check_zigpy_connection(
            mock.sentinel.usb_path, mock.sentinel.unk_radio, mock.sentinel.zigbee_db
        )
        assert mock_radio.connect.call_count == 0
        assert bad_radio.connect.call_count == 0
        assert mock_ctrl.startup.call_count == 0
        assert mock_ctrl.shutdown.call_count == 0

        # unsuccessful radio connect
        assert not await config_flow.check_zigpy_connection(
            mock.sentinel.usb_path, mock.sentinel.bad_radio, mock.sentinel.zigbee_db
        )
        assert mock_radio.connect.call_count == 0
        assert bad_radio.connect.call_count == 1
        assert mock_ctrl.startup.call_count == 0
        assert mock_ctrl.shutdown.call_count == 0

        # successful radio connect
        assert await config_flow.check_zigpy_connection(
            mock.sentinel.usb_path, mock.sentinel.radio, mock.sentinel.zigbee_db
        )
        assert mock_radio.connect.call_count == 1
        assert bad_radio.connect.call_count == 1
        assert mock_ctrl.startup.call_count == 1
        assert mock_ctrl.shutdown.call_count == 1
