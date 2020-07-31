"""Test the Shark IQ config flow."""
from copy import deepcopy
import enum

from sharkiqpy import AylaApi, Properties, SharkIqVacuum

from homeassistant.components.sharkiq import SharkIqUpdateCoordinator
from homeassistant.components.sharkiq.sharkiq import (
    ATTR_ERROR_CODE,
    ATTR_ERROR_MSG,
    ATTR_LOW_LIGHT,
    ATTR_RECHARGE_RESUME,
    ATTR_RSSI,
    STATE_RECHARGING_TO_RESUME,
    SharkVacuumEntity,
)
from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
)
from homeassistant.core import HomeAssistant

from .const import SHARK_DEVICE_DICT, SHARK_PROPERTIES_DICT

from tests.async_mock import MagicMock, patch

try:
    import ujson as json
except ImportError:
    import json


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
    assert shark.state == STATE_RECHARGING_TO_RESUME

    shark.sharkiq.set_property_value(Properties.RECHARGING_TO_RESUME, 0)
    assert shark.state == STATE_DOCKED


@patch.object(SharkIqVacuum, "set_property_value", new=_set_property)
@patch.object(SharkIqVacuum, "async_set_property_value", new=_async_set_property)
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
        ATTR_RSSI: -46,
        ATTR_ERROR_CODE: 7,
        ATTR_ERROR_MSG: "Cliff sensor is blocked",
        ATTR_RECHARGE_RESUME: True,
        ATTR_LOW_LIGHT: False,
    }
    state_json = json.dumps(shark.shark_state_attributes, sort_keys=True)
    target_json = json.dumps(target_state_attributes, sort_keys=True)
    assert state_json == target_json
