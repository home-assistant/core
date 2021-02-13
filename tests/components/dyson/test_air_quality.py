"""Test the Dyson air quality component."""

from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_state_v2 import DysonEnvironmentalSensorV2State

from homeassistant.components.air_quality import (
    ATTR_AQI,
    ATTR_NO2,
    ATTR_PM_2_5,
    ATTR_PM_10,
    DOMAIN as PLATFORM_DOMAIN,
)
from homeassistant.components.dyson.air_quality import ATTR_VOC
from homeassistant.core import HomeAssistant, callback

from .common import ENTITY_NAME, async_get_purecool_device, async_update_device

ENTITY_ID = f"{PLATFORM_DOMAIN}.{ENTITY_NAME}"

MOCKED_VALUES = {
    ATTR_PM_2_5: 10,
    ATTR_PM_10: 20,
    ATTR_NO2: 30,
    ATTR_VOC: 40,
}

MOCKED_UPDATED_VALUES = {
    ATTR_PM_2_5: 60,
    ATTR_PM_10: 50,
    ATTR_NO2: 40,
    ATTR_VOC: 30,
}


def _async_assign_values(device: DysonPureCool, values=MOCKED_VALUES) -> None:
    """Assign mocked environmental states to the device."""
    device.environmental_state.particulate_matter_25 = values[ATTR_PM_2_5]
    device.environmental_state.particulate_matter_10 = values[ATTR_PM_10]
    device.environmental_state.nitrogen_dioxide = values[ATTR_NO2]
    device.environmental_state.volatile_organic_compounds = values[ATTR_VOC]


@callback
def async_get_device() -> DysonPureCool:
    """Return a device of the given type."""
    device = async_get_purecool_device()
    _async_assign_values(device)
    return device


async def test_air_quality(hass: HomeAssistant, device: DysonPureCool) -> None:
    """Test the state and attributes of the air quality entity."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == str(MOCKED_VALUES[ATTR_PM_2_5])
    attributes = state.attributes
    for attr, value in MOCKED_VALUES.items():
        assert attributes[attr] == value
    assert attributes[ATTR_AQI] == 40

    _async_assign_values(device, MOCKED_UPDATED_VALUES)
    await async_update_device(hass, device, DysonEnvironmentalSensorV2State)
    state = hass.states.get(ENTITY_ID)
    assert state.state == str(MOCKED_UPDATED_VALUES[ATTR_PM_2_5])
    attributes = state.attributes
    for attr, value in MOCKED_UPDATED_VALUES.items():
        assert attributes[attr] == value
    assert attributes[ATTR_AQI] == 60
