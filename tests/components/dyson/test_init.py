"""Test the parent Dyson component."""
import copy
import logging
from unittest.mock import MagicMock, patch

from homeassistant.components.dyson import DOMAIN
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant

from .common import (
    BASE_PATH,
    CONFIG,
    ENTITY_NAME,
    IP_ADDRESS,
    async_get_360eye_device,
    async_get_purecool_device,
    async_get_purecoollink_device,
)

from tests.common import async_setup_component


async def test_setup_manual(hass: HomeAssistant, caplog):
    """Test set up the component with manually configured device IPs."""
    SERIAL_TEMPLATE = "XX-XXXXX-X{}"

    # device1 works
    device1 = async_get_purecoollink_device()
    device1.serial = SERIAL_TEMPLATE.format(1)

    # device2 failed to connect
    device2 = async_get_purecool_device()
    device2.serial = SERIAL_TEMPLATE.format(2)
    device2.connect = MagicMock(return_value=False)

    # device3 throws exception during connection
    device3 = async_get_360eye_device()
    device3.serial = SERIAL_TEMPLATE.format(3)
    device3.connect = MagicMock(side_effect=OSError("error msg"))

    # device4 not configured in configuration
    device4 = async_get_360eye_device()
    device4.serial = SERIAL_TEMPLATE.format(4)

    devices = [device1, device2, device3, device4]
    config = copy.deepcopy(CONFIG)
    config[DOMAIN][CONF_DEVICES] = [
        {
            "device_id": SERIAL_TEMPLATE.format(i),
            "device_ip": IP_ADDRESS,
        }
        for i in [1, 2, 3, 5]  # 1 device missing and 1 device not existed
    ]

    with patch(f"{BASE_PATH}.DysonAccount.login", return_value=True) as login, patch(
        f"{BASE_PATH}.DysonAccount.devices", return_value=devices
    ) as devices_method, patch(
        f"{BASE_PATH}.DYSON_PLATFORMS", ["fan", "vacuum"]
    ):  # Patch platforms to get rid of sensors
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()
    login.assert_called_once_with()
    devices_method.assert_called_once_with()

    # Only one fan and zero vacuum is set up successfully
    assert hass.states.async_entity_ids() == [f"fan.{ENTITY_NAME}"]
    device1.connect.assert_called_once_with(IP_ADDRESS)
    device2.connect.assert_called_once_with(IP_ADDRESS)
    device3.connect.assert_called_once_with(IP_ADDRESS)
    device4.connect.assert_not_called()
    assert (
        BASE_PATH,
        logging.WARNING,
        f"Unable to connect to device {device2}",
    ) in caplog.record_tuples
    assert (
        BASE_PATH,
        logging.ERROR,
        f"Unable to connect to device {device3.network_device}: error msg",
    ) in caplog.record_tuples
    (
        BASE_PATH,
        logging.WARNING,
        f"Unable to find device {SERIAL_TEMPLATE.format(5)} in Dyson account",
    ) in caplog.record_tuples


async def test_setup_autoconnect(hass: HomeAssistant, caplog):
    """Test set up the component with auto connect."""
    # device1 works
    device1 = async_get_purecoollink_device()

    # device2 failed to auto connect
    device2 = async_get_purecool_device()
    device2.auto_connect = MagicMock(return_value=False)

    devices = [device1, device2]
    config = copy.deepcopy(CONFIG)
    config[DOMAIN].pop(CONF_DEVICES)

    with patch(f"{BASE_PATH}.DysonAccount.login", return_value=True), patch(
        f"{BASE_PATH}.DysonAccount.devices", return_value=devices
    ), patch(
        f"{BASE_PATH}.DYSON_PLATFORMS", ["fan"]
    ):  # Patch platforms to get rid of sensors
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()

    assert hass.states.async_entity_ids_count() == 1
    assert (
        BASE_PATH,
        logging.WARNING,
        f"Unable to connect to device {device2}",
    ) in caplog.record_tuples


async def test_login_failed(hass: HomeAssistant, caplog):
    """Test login failure during setup."""
    with patch(f"{BASE_PATH}.DysonAccount.login", return_value=False):
        assert await async_setup_component(hass, DOMAIN, CONFIG) is False
        await hass.async_block_till_done()
    assert (
        BASE_PATH,
        logging.ERROR,
        "Not connected to Dyson account. Unable to add devices",
    ) in caplog.record_tuples
