"""Tests for the Homematic integration."""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.homematic.const import (
    ATTR_ADDRESS,
    ATTR_CHANNEL,
    ATTR_INTERFACE,
    ATTR_PARAM,
    ATTR_PARAMSET,
    ATTR_PARAMSET_KEY,
    ATTR_VALUE,
    ATTR_VALUE_TYPE,
    DATA_HOMEMATIC,
    SERVICE_PUT_PARAMSET,
    SERVICE_RECONNECT,
    SERVICE_SET_DEVICE_VALUE,
    SERVICE_SET_INSTALL_MODE,
    SERVICE_SET_VARIABLE_VALUE,
    SERVICE_VIRTUALKEY,
)
from homeassistant.components.homematic.entity import HMHub
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

DOMAIN = "homematic"
BASE_CONFIG = {DOMAIN: {"hosts": {"ccu2": {"host": "127.0.0.1"}}}}


@pytest.fixture
async def setup_homematic(hass: HomeAssistant) -> None:
    """Set up the homematic component."""
    with patch(
        "homeassistant.components.homematic.HMConnection",
        return_value=MagicMock(),
    ):
        await async_setup_component(hass, DOMAIN, BASE_CONFIG)
        await hass.async_block_till_done()


async def test_set_install_mode_admin_allowed(
    hass: HomeAssistant,
    setup_homematic: None,
    hass_admin_user: MockUser,
) -> None:
    """Test that admin users can call set_install_mode."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_INSTALL_MODE,
        {ATTR_INTERFACE: "ccu2"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    hass.data[DATA_HOMEMATIC].setInstallMode.assert_called_once_with(
        "ccu2", t=60, mode=1, address=None
    )


async def test_set_install_mode_non_admin_rejected(
    hass: HomeAssistant,
    setup_homematic: None,
    hass_read_only_user: MockUser,
) -> None:
    """Test that non-admin users cannot call set_install_mode."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_INSTALL_MODE,
            {ATTR_INTERFACE: "ccu2"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )


@pytest.mark.usefixtures("setup_homematic")
async def test_reconnect(hass: HomeAssistant) -> None:
    """Test the reconnect action."""
    await hass.services.async_call(DOMAIN, SERVICE_RECONNECT, blocking=True)
    hass.data[DATA_HOMEMATIC].reconnect.assert_called_once_with()


@pytest.mark.usefixtures("setup_homematic")
async def test_put_paramset(hass: HomeAssistant) -> None:
    """Test the put_paramset action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUT_PARAMSET,
        {
            ATTR_INTERFACE: "ccu2",
            ATTR_ADDRESS: "abc123",
            ATTR_PARAMSET_KEY: "master",
            ATTR_PARAMSET: {"WEEK_PROGRAM_POINTER": 1},
        },
        blocking=True,
    )
    hass.data[DATA_HOMEMATIC].putParamset.assert_called_once_with(
        "ccu2", "ABC123", "MASTER", {"WEEK_PROGRAM_POINTER": 1}, None
    )


@pytest.fixture
def hm_device(hass: HomeAssistant, setup_homematic: None) -> MagicMock:
    """Add a device to the mocked homematic connection."""
    device = MagicMock(ACTIONNODE={"PRESS_SHORT": [1]})
    hass.data[DATA_HOMEMATIC].devices = {"ccu2": {"ABC123": device}}
    return device


@pytest.mark.parametrize(
    "extra_data",
    [
        pytest.param({}, id="any_interface"),
        pytest.param({ATTR_INTERFACE: "ccu2"}, id="interface"),
    ],
)
async def test_virtualkey(
    hass: HomeAssistant, hm_device: MagicMock, extra_data: dict[str, str]
) -> None:
    """Test the virtualkey action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_VIRTUALKEY,
        {
            ATTR_ADDRESS: "abc123",
            ATTR_CHANNEL: 1,
            ATTR_PARAM: "PRESS_SHORT",
            **extra_data,
        },
        blocking=True,
    )
    hm_device.actionNodeData.assert_called_once_with("PRESS_SHORT", True, 1)


@pytest.mark.parametrize(
    ("address", "device_address"),
    [
        pytest.param("bidcos-rf", "BidCoS-RF", id="bidcos_rf"),
        pytest.param("hmip-rcv-1", "HmIP-RCV-1", id="hmip_rcv_1"),
    ],
)
async def test_virtualkey_mixed_case_address(
    hass: HomeAssistant, hm_device: MagicMock, address: str, device_address: str
) -> None:
    """Test the virtualkey action restores the case of the central addresses."""
    hass.data[DATA_HOMEMATIC].devices = {"ccu2": {device_address: hm_device}}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_VIRTUALKEY,
        {ATTR_ADDRESS: address, ATTR_CHANNEL: 1, ATTR_PARAM: "PRESS_SHORT"},
        blocking=True,
    )
    hm_device.actionNodeData.assert_called_once_with("PRESS_SHORT", True, 1)


@pytest.mark.parametrize(
    ("address", "channel", "param", "message"),
    [
        pytest.param(
            "unknown", 1, "PRESS_SHORT", "UNKNOWN not found", id="unknown_device"
        ),
        pytest.param(
            "abc123", 1, "UNKNOWN", "UNKNOWN not datapoint", id="unknown_param"
        ),
        pytest.param(
            "abc123", 2, "PRESS_SHORT", "2 is not a channel", id="unknown_channel"
        ),
    ],
)
async def test_virtualkey_invalid_target(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    hm_device: MagicMock,
    address: str,
    channel: int,
    param: str,
    message: str,
) -> None:
    """Test the virtualkey action logs an error for an invalid target."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_VIRTUALKEY,
        {ATTR_ADDRESS: address, ATTR_CHANNEL: channel, ATTR_PARAM: param},
        blocking=True,
    )
    assert message in caplog.text
    hm_device.actionNodeData.assert_not_called()


@pytest.mark.parametrize(
    ("value", "value_type", "expected"),
    [
        pytest.param("1", "int", 1, id="int"),
        pytest.param("1.5", "double", 1.5, id="double"),
        pytest.param(1, "boolean", True, id="boolean"),
        pytest.param(
            "20261105T10:20:30",
            "dateTime.iso8601",
            datetime(2026, 11, 5, 10, 20, 30),
            id="datetime",
        ),
        pytest.param(1, "string", "1", id="string"),
    ],
)
async def test_set_device_value(
    hass: HomeAssistant,
    hm_device: MagicMock,
    value: Any,
    value_type: str,
    expected: Any,
) -> None:
    """Test the set_device_value action converts the value."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEVICE_VALUE,
        {
            ATTR_ADDRESS: "abc123",
            ATTR_CHANNEL: 1,
            ATTR_PARAM: "state",
            ATTR_VALUE: value,
            ATTR_VALUE_TYPE: value_type,
        },
        blocking=True,
    )
    hm_device.setValue.assert_called_once_with("STATE", expected, 1)


async def test_set_device_value_unknown_device(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, hm_device: MagicMock
) -> None:
    """Test the set_device_value action logs an error for an unknown device."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DEVICE_VALUE,
        {ATTR_ADDRESS: "unknown", ATTR_CHANNEL: 1, ATTR_PARAM: "state", ATTR_VALUE: 1},
        blocking=True,
    )
    assert "UNKNOWN not found!" in caplog.text
    hm_device.setValue.assert_not_called()


@pytest.mark.parametrize(
    "extra_data",
    [
        pytest.param({}, id="all_hubs"),
        pytest.param({ATTR_ENTITY_ID: "homematic.ccu2"}, id="entity_id"),
    ],
)
@pytest.mark.usefixtures("setup_homematic")
async def test_set_variable_value(
    hass: HomeAssistant, extra_data: dict[str, str]
) -> None:
    """Test the set_variable_value action."""
    with patch.object(HMHub, "hm_set_variable") as mock_set_variable:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VARIABLE_VALUE,
            {ATTR_NAME: "my_variable", ATTR_VALUE: 1, **extra_data},
            blocking=True,
        )
    mock_set_variable.assert_called_once_with("my_variable", 1)


@pytest.mark.usefixtures("setup_homematic")
async def test_set_variable_value_unknown_hub(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the set_variable_value action logs an error without a matching hub."""
    with patch.object(HMHub, "hm_set_variable") as mock_set_variable:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VARIABLE_VALUE,
            {
                ATTR_NAME: "my_variable",
                ATTR_VALUE: 1,
                ATTR_ENTITY_ID: "homematic.other",
            },
            blocking=True,
        )
    assert "No HomeMatic hubs available" in caplog.text
    mock_set_variable.assert_not_called()
