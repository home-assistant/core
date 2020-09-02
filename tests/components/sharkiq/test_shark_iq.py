"""Test the Shark IQ vacuum entity."""
from copy import deepcopy
from pprint import pprint, pformat
import enum
import json
import logging
from typing import Dict, List

import pytest
from sharkiqpy import AylaApi, Properties, SharkIqAuthError, SharkIqVacuum, get_ayla_api

from homeassistant.components.sharkiq import DOMAIN, SharkIqUpdateCoordinator
from homeassistant.components.sharkiq.vacuum import (
    ATTR_ERROR_CODE,
    ATTR_ERROR_MSG,
    ATTR_LOW_LIGHT,
    ATTR_RECHARGE_RESUME,
    SharkVacuumEntity,
)
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_PARAMS,
    ATTR_STATUS,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    SUPPORT_BATTERY,
    SUPPORT_FAN_SPEED,
    SUPPORT_LOCATE,
    SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
    SUPPORT_STATE,
    SUPPORT_STATUS,
    SUPPORT_STOP,
)
from homeassistant.config_entries import ConfigEntriesFlowManager, ConfigEntry
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CONFIG,
    SHARK_DEVICE_DICT,
    SHARK_METADATA_DICT,
    SHARK_PROPERTIES_DICT,
    TEST_PASSWORD,
    TEST_USERNAME,
)
from ..vacuum import common

from tests.async_mock import patch
from tests.common import MockConfigEntry

VAC_ENTITY_ID = f"vacuum.{SHARK_DEVICE_DICT['product_name'].lower()}"
_LOGGER = logging.getLogger(__name__)


class MockAyla(AylaApi):
    """Mocked AylaApi that doesn't do anything."""
    async def async_sign_in(self):
        """Instead of signing in, just return."""
        pass

    async def async_list_devices(self) -> List[dict]:
        """Return the device list."""
        return [SHARK_DEVICE_DICT]

    async def async_get_devices(self, update: bool = True) -> List[SharkIqVacuum]:
        """Get the list of devices."""
        shark = SharkIqVacuum(self, SHARK_DEVICE_DICT)
        shark.properties_full = deepcopy(SHARK_PROPERTIES_DICT)
        shark._update_metadata(SHARK_METADATA_DICT)  # pylint: disable=protected-access
        return [shark]


def _set_property(self, property_name, value):
    """Set a property locally without hitting the API."""
    if isinstance(property_name, enum.Enum):
        property_name = property_name.value
    if isinstance(value, enum.Enum):
        value = value.value
    self.properties_full[property_name]["value"] = value


async def _async_set_property(self, property_name, value):
    """Set a property locally without hitting the API."""
    print(f"Setting {id(self)}/{property_name} to {value}")
    _set_property(self, property_name, value)


async def async_nop(*args, **kwargs):
    """Don't do nothin'."""
    pass


@pytest.fixture(autouse=True)
@patch('sharkiqpy.ayla_api.AylaApi', MockAyla)
@patch.object(SharkIqUpdateCoordinator, "_async_update_vacuum", new=async_nop)
async def setup_integration(hass):
    """Setup the mock integration"""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=TEST_USERNAME, data=CONFIG)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def assert_attributes(state,  **kwargs):
    """Assert expected properties."""
    for attr, value in kwargs.items():
        assert state.attributes.get(attr) == value


async def test_simple_properties(hass: HomeAssistant):
    """Test that simple properties work as intended."""
    state = hass.states.get(VAC_ENTITY_ID)
    registry = await hass.helpers.entity_registry.async_get_registry()
    entity = registry.async_get(VAC_ENTITY_ID)

    assert entity
    assert state
    assert entity.unique_id == "AC000Wxxxxxxxxx"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == (
        SUPPORT_BATTERY
        | SUPPORT_FAN_SPEED
        | SUPPORT_PAUSE
        | SUPPORT_RETURN_HOME
        | SUPPORT_START
        | SUPPORT_STATE
        | SUPPORT_STATUS
        | SUPPORT_STOP
        | SUPPORT_LOCATE
    )
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 50
    assert state.attributes.get(ATTR_FAN_SPEED) == "Eco"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == ["Eco", "Normal", "Max"]
    assert state.attributes.get(ATTR_ERROR_CODE) == 7
    assert state.attributes.get(ATTR_ERROR_MSG) == "Cliff sensor is blocked"
    assert not state.attributes.get(ATTR_LOW_LIGHT, True)
    assert state.attributes.get(ATTR_RECHARGE_RESUME)


@patch.object(SharkIqVacuum, "set_property_value", new=_set_property)
@patch.object(SharkIqVacuum, "async_set_property_value", new=_async_set_property)
@patch.object(SharkIqUpdateCoordinator, "_async_update_vacuum", new=async_nop)
async def test_shark_methods(hass: HomeAssistant) -> None:
    """Test all of the shark vacuum operation modes."""

    state = hass.states.get(VAC_ENTITY_ID)
    assert state.state == STATE_CLEANING

    await common.async_stop(hass, VAC_ENTITY_ID)
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.state == STATE_IDLE

    await common.async_pause(hass, VAC_ENTITY_ID)
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.state == STATE_PAUSED

    await common.async_return_to_base(hass, VAC_ENTITY_ID)
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.state == STATE_RETURNING

    await common.async_set_fan_speed(
        hass, "Max", entity_id=VAC_ENTITY_ID
    )
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "Max"

    await common.async_set_fan_speed(
        hass, "Normal", entity_id=VAC_ENTITY_ID
    )
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "Normal"

    await common.async_set_fan_speed(
        hass, "Eco", entity_id=VAC_ENTITY_ID
    )
    state = hass.states.get(VAC_ENTITY_ID)
    assert state.attributes.get(ATTR_FAN_SPEED) == "Eco"


async def test_device(hass: HomeAssistant):
    """Test device properties"""
    registry = await hass.helpers.device_registry.async_get_registry()
    device = registry.async_get_device({(DOMAIN, "AC000Wxxxxxxxxx")}, [])
    assert device.manufacturer == "Shark"
    assert device.model == "RV1001AE"
    assert device.name == "Sharknado"
    assert device.sw_version == "Dummy Firmware 1.0"


#     assert not shark.should_poll
#
#
#
#
def _get_async_update(err=None):
    async def _async_update(_) -> bool:
        if err is not None:
            raise err
        return True
    return _async_update


@patch('sharkiqpy.ayla_api.AylaApi', MockAyla)
async def test_updates(hass: HomeAssistant) -> None:
    """Test the update coordinator update functions."""
    ayla_api = get_ayla_api(TEST_USERNAME, TEST_PASSWORD)
    shark_vacs = await ayla_api.async_get_devices()
    mock_config = MockConfigEntry(domain=DOMAIN, unique_id=TEST_USERNAME, data=CONFIG)
    coordinator = SharkIqUpdateCoordinator(hass, mock_config, ayla_api, shark_vacs)

    with patch.object(SharkIqVacuum, "async_update", new=_get_async_update()):
        update_called = await coordinator._async_update_data()  # pylint: disable=protected-access
        assert update_called

    update_failed = False
    with patch.object(
        SharkIqVacuum, "async_update", new=_get_async_update(SharkIqAuthError)
    ), patch.object(HomeAssistant, "async_create_task"), patch.object(
        ConfigEntriesFlowManager, "async_init"
    ):
        try:
            await coordinator._async_update_data()  # pylint: disable=protected-access
        except UpdateFailed:
            update_failed = True
    assert update_failed
