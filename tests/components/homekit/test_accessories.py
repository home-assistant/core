"""Test all functions related to the basic accessory implementation.

This includes tests for all mock object types.
"""

from unittest.mock import patch

# pylint: disable=unused-import
from pyhap.loader import get_serv_loader, get_char_loader  # noqa F401

from homeassistant.components.homekit.accessories import (
    set_accessory_info, add_preload_service, override_properties,
    HomeAccessory, HomeBridge)
from homeassistant.components.homekit.const import (
    SERV_ACCESSORY_INFO, SERV_BRIDGING_STATE,
    CHAR_MODEL, CHAR_MANUFACTURER, CHAR_NAME, CHAR_SERIAL_NUMBER)

from tests.mock.homekit import (
    get_patch_paths, mock_preload_service,
    MockTypeLoader, MockAccessory, MockService, MockChar)

PATH_SERV = 'pyhap.loader.get_serv_loader'
PATH_CHAR = 'pyhap.loader.get_char_loader'
PATH_ACC, _ = get_patch_paths()


@patch(PATH_CHAR, return_value=MockTypeLoader('char'))
@patch(PATH_SERV, return_value=MockTypeLoader('service'))
def test_add_preload_service(mock_serv, mock_char):
    """Test method add_preload_service.

    The methods 'get_serv_loader' and 'get_char_loader' are mocked.
    """
    acc = MockAccessory('Accessory')
    serv = add_preload_service(acc, 'TestService',
                               ['TestChar', 'TestChar2'],
                               ['TestOptChar', 'TestOptChar2'])

    assert serv.display_name == 'TestService'
    assert len(serv.characteristics) == 2
    assert len(serv.opt_characteristics) == 2

    acc.services = []
    serv = add_preload_service(acc, 'TestService')

    assert not serv.characteristics
    assert not serv.opt_characteristics

    acc.services = []
    serv = add_preload_service(acc, 'TestService',
                               'TestChar', 'TestOptChar')

    assert len(serv.characteristics) == 1
    assert len(serv.opt_characteristics) == 1

    assert serv.characteristics[0].display_name == 'TestChar'
    assert serv.opt_characteristics[0].display_name == 'TestOptChar'


def test_override_properties():
    """Test override of characteristic properties with MockChar."""
    char = MockChar('TestChar')
    new_prop = {1: 'Test', 2: 'Demo'}
    override_properties(char, new_prop)

    assert char.properties == new_prop


def test_set_accessory_info():
    """Test setting of basic accessory information with MockAccessory."""
    acc = MockAccessory('Accessory')
    set_accessory_info(acc, 'name', 'model', 'manufacturer', '0000')

    assert len(acc.services) == 1
    serv = acc.services[0]

    assert serv.display_name == SERV_ACCESSORY_INFO
    assert len(serv.characteristics) == 4
    chars = serv.characteristics

    assert chars[0].display_name == CHAR_NAME
    assert chars[0].value == 'name'
    assert chars[1].display_name == CHAR_MODEL
    assert chars[1].value == 'model'
    assert chars[2].display_name == CHAR_MANUFACTURER
    assert chars[2].value == 'manufacturer'
    assert chars[3].display_name == CHAR_SERIAL_NUMBER
    assert chars[3].value == '0000'


@patch(PATH_ACC, side_effect=mock_preload_service)
def test_home_accessory(mock_pre_serv):
    """Test initializing a HomeAccessory object."""
    acc = HomeAccessory('TestAccessory', 'test.accessory', 'WINDOW')

    assert acc.display_name == 'TestAccessory'
    assert acc.category == 13  # Category.WINDOW
    assert len(acc.services) == 1

    serv = acc.services[0]
    assert serv.display_name == SERV_ACCESSORY_INFO
    char_model = serv.get_characteristic(CHAR_MODEL)
    assert char_model.get_value() == 'test.accessory'


@patch(PATH_ACC, side_effect=mock_preload_service)
def test_home_bridge(mock_pre_serv):
    """Test initializing a HomeBridge object."""
    bridge = HomeBridge('TestBridge', 'test.bridge', b'123-45-678')

    assert bridge.display_name == 'TestBridge'
    assert bridge.pincode == b'123-45-678'
    assert len(bridge.services) == 2

    assert bridge.services[0].display_name == SERV_ACCESSORY_INFO
    assert bridge.services[1].display_name == SERV_BRIDGING_STATE

    char_model = bridge.services[0].get_characteristic(CHAR_MODEL)
    assert char_model.get_value() == 'test.bridge'


def test_mock_accessory():
    """Test attributes and functions of a MockAccessory."""
    acc = MockAccessory('TestAcc')
    serv = MockService('TestServ')
    acc.add_service(serv)

    assert acc.display_name == 'TestAcc'
    assert len(acc.services) == 1

    assert acc.get_service('TestServ') == serv
    assert acc.get_service('NewServ').display_name == 'NewServ'
    assert len(acc.services) == 2


def test_mock_service():
    """Test attributes and functions of a MockService."""
    serv = MockService('TestServ')
    char = MockChar('TestChar')
    opt_char = MockChar('TestOptChar')
    serv.add_characteristic(char)
    serv.add_opt_characteristic(opt_char)

    assert serv.display_name == 'TestServ'
    assert len(serv.characteristics) == 1
    assert len(serv.opt_characteristics) == 1

    assert serv.get_characteristic('TestChar') == char
    assert serv.get_characteristic('TestOptChar') == opt_char
    assert serv.get_characteristic('NewChar').display_name == 'NewChar'
    assert len(serv.characteristics) == 2


def test_mock_char():
    """Test attributes and functions of a MockChar."""
    def callback_method(value):
        """Provide a callback options for 'set_value' method."""
        assert value == 'With callback'

    char = MockChar('TestChar')
    char.set_value('Value')

    assert char.display_name == 'TestChar'
    assert char.get_value() == 'Value'

    char.setter_callback = callback_method
    char.set_value('With callback')
