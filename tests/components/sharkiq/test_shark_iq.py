"""Test the Shark IQ vacuum entity."""
from copy import deepcopy
import enum
import json
from typing import Dict, List

from sharkiqpy import AylaApi, Properties, SharkIqAuthError, SharkIqVacuum, get_ayla_api

from homeassistant.components.sharkiq import SharkIqUpdateCoordinator
from homeassistant.components.sharkiq.vacuum import (
    ATTR_ERROR_CODE,
    ATTR_ERROR_MSG,
    ATTR_LOW_LIGHT,
    ATTR_RECHARGE_RESUME,
    SharkVacuumEntity,
)
from homeassistant.components.vacuum import (
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    SHARK_DEVICE_DICT,
    SHARK_METADATA_DICT,
    SHARK_PROPERTIES_DICT,
    TEST_PASSWORD,
    TEST_USERNAME,
)

from tests.async_mock import MagicMock, patch

MockAyla = MagicMock(spec=AylaApi)  # pylint: disable=invalid-name


def _set_property(self, property_name, value):
    """Set a property locally without hitting the API."""
    if isinstance(property_name, enum.Enum):
        property_name = property_name.value
    if isinstance(value, enum.Enum):
        value = value.value
    self.properties_full[property_name]["value"] = value


async def _async_set_property(self, property_name, value):
    """Set a property locally without hitting the API."""
    _set_property(self, property_name, value)


def _get_mock_shark_vac(ayla_api: AylaApi) -> SharkIqVacuum:
    """Create a crude sharkiq vacuum with mocked properties."""
    shark = SharkIqVacuum(ayla_api, SHARK_DEVICE_DICT)
    shark.properties_full = deepcopy(SHARK_PROPERTIES_DICT)
    return shark


async def _async_list_devices(_) -> List[Dict]:
    """Generate a dummy of async_list_devices output."""
    return [SHARK_DEVICE_DICT]


@patch.object(SharkIqVacuum, "set_property_value", new=_set_property)
@patch.object(SharkIqVacuum, "async_set_property_value", new=_async_set_property)
async def test_shark_operation_modes(hass: HomeAssistant) -> None:
    """Test all of the shark vacuum operation modes."""
    ayla_api = MockAyla()
    shark_vac = _get_mock_shark_vac(ayla_api)
    coordinator = SharkIqUpdateCoordinator(hass, None, ayla_api, [shark_vac])
    shark = SharkVacuumEntity(shark_vac, coordinator)

    # These come from the setup
    assert isinstance(shark.is_docked, bool) and not shark.is_docked
    assert (
        isinstance(shark.recharging_to_resume, bool) and not shark.recharging_to_resume
    )
    # Go through the operation modes while it's "off the dock"
    await shark.async_start()
    assert shark.operating_mode == shark.state == STATE_CLEANING
    await shark.async_pause()
    assert shark.operating_mode == shark.state == STATE_PAUSED
    await shark.async_stop()
    assert shark.operating_mode == shark.state == STATE_IDLE
    await shark.async_return_to_base()
    assert shark.operating_mode == shark.state == STATE_RETURNING

    # Test the docked modes
    await shark.async_stop()
    shark.sharkiq.set_property_value(Properties.RECHARGING_TO_RESUME, 1)
    shark.sharkiq.set_property_value(Properties.DOCKED_STATUS, 1)
    assert isinstance(shark.is_docked, bool) and shark.is_docked
    assert isinstance(shark.recharging_to_resume, bool) and shark.recharging_to_resume
    assert shark.state == STATE_DOCKED

    shark.sharkiq.set_property_value(Properties.RECHARGING_TO_RESUME, 0)
    assert shark.state == STATE_DOCKED

    await shark.async_set_fan_speed("Eco")
    assert shark.fan_speed == "Eco"
    await shark.async_set_fan_speed("Max")
    assert shark.fan_speed == "Max"
    await shark.async_set_fan_speed("Normal")
    assert shark.fan_speed == "Normal"

    assert set(shark.fan_speed_list) == {"Normal", "Max", "Eco"}


@patch.object(SharkIqVacuum, "set_property_value", new=_set_property)
async def test_shark_vac_properties(hass: HomeAssistant) -> None:
    """Test all of the shark vacuum property accessors."""
    ayla_api = MockAyla()
    shark_vac = _get_mock_shark_vac(ayla_api)
    coordinator = SharkIqUpdateCoordinator(hass, None, ayla_api, [shark_vac])
    shark = SharkVacuumEntity(shark_vac, coordinator)

    assert shark.name == "Sharknado"
    assert shark.serial_number == "AC000Wxxxxxxxxx"
    assert shark.model == "RV1000A"

    assert shark.battery_level == 50
    assert shark.fan_speed == "Eco"
    shark.sharkiq.set_property_value(Properties.POWER_MODE, 0)
    assert shark.fan_speed == "Normal"
    assert isinstance(shark.recharge_resume, bool) and shark.recharge_resume
    assert isinstance(shark.low_light, bool) and not shark.low_light

    target_state_attributes = {
        ATTR_ERROR_CODE: 7,
        ATTR_ERROR_MSG: "Cliff sensor is blocked",
        ATTR_RECHARGE_RESUME: True,
        ATTR_LOW_LIGHT: False,
    }
    state_json = json.dumps(shark.device_state_attributes, sort_keys=True)
    target_json = json.dumps(target_state_attributes, sort_keys=True)
    assert state_json == target_json

    assert not shark.should_poll


@patch.object(SharkIqVacuum, "set_property_value", new=_set_property)
@patch.object(SharkIqVacuum, "async_set_property_value", new=_async_set_property)
async def test_shark_metadata(hass: HomeAssistant) -> None:
    """Test shark properties coming from metadata."""
    ayla_api = MockAyla()
    shark_vac = _get_mock_shark_vac(ayla_api)
    coordinator = SharkIqUpdateCoordinator(hass, None, ayla_api, [shark_vac])
    shark = SharkVacuumEntity(shark_vac, coordinator)
    shark.sharkiq._update_metadata(  # pylint: disable=protected-access
        SHARK_METADATA_DICT
    )

    target_device_info = {
        "identifiers": {("sharkiq", "AC000Wxxxxxxxxx")},
        "name": "Sharknado",
        "manufacturer": "Shark",
        "model": "RV1001AE",
        "sw_version": "Dummy Firmware 1.0",
    }

    assert shark.device_info == target_device_info


def _get_async_update(err=None):
    async def _async_update(_) -> bool:
        if err is not None:
            raise err
        return True

    return _async_update


@patch.object(AylaApi, "async_list_devices", new=_async_list_devices)
async def test_updates(hass: HomeAssistant) -> None:
    """Test the update coordinator update functions."""
    ayla_api = get_ayla_api(TEST_USERNAME, TEST_PASSWORD)
    shark_vac = _get_mock_shark_vac(ayla_api)
    mock_config = MagicMock(spec=ConfigEntry)
    coordinator = SharkIqUpdateCoordinator(hass, mock_config, ayla_api, [shark_vac])

    with patch.object(SharkIqVacuum, "async_update", new=_get_async_update()):
        update_called = (
            await coordinator._async_update_data()  # pylint: disable=protected-access
        )
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


async def test_coordinator_match(hass: HomeAssistant):
    """Test that sharkiq-coordinator references work."""
    ayla_api = get_ayla_api(TEST_PASSWORD, TEST_USERNAME)
    shark_vac1 = _get_mock_shark_vac(ayla_api)
    shark_vac2 = _get_mock_shark_vac(ayla_api)
    shark_vac2._dsn = "FOOBAR!"  # pylint: disable=protected-access

    coordinator = SharkIqUpdateCoordinator(hass, None, ayla_api, [shark_vac1])

    api = SharkVacuumEntity(shark_vac1, coordinator)
    coordinator.last_update_success = True
    coordinator._online_dsns = set()  # pylint: disable=protected-access
    assert not api.is_online
    assert not api.available

    coordinator._online_dsns = {  # pylint: disable=protected-access
        shark_vac1.serial_number
    }
    assert api.is_online
    assert api.available

    coordinator.last_update_success = False
    assert not api.available


async def test_simple_properties(hass: HomeAssistant):
    """Test that simple properties work as intended."""
    ayla_api = get_ayla_api(TEST_PASSWORD, TEST_USERNAME)
    shark_vac1 = _get_mock_shark_vac(ayla_api)
    coordinator = SharkIqUpdateCoordinator(hass, None, ayla_api, [shark_vac1])
    entity = SharkVacuumEntity(shark_vac1, coordinator)

    assert entity.unique_id == "AC000Wxxxxxxxxx"

    assert entity.supported_features == (
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

    assert entity.error_code == 7
    assert entity.error_message == "Cliff sensor is blocked"
    shark_vac1.properties_full[Properties.ERROR_CODE.value]["value"] = 0
    assert entity.error_code == 0
    assert entity.error_message is None

    assert (
        coordinator.online_dsns
        is coordinator._online_dsns  # pylint: disable=protected-access
    )
