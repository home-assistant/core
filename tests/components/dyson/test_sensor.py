"""Test the Dyson sensor(s) component."""
from typing import List, Type
from unittest.mock import patch

from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_cool_link import DysonPureCoolLink
import pytest

from homeassistant.components.dyson import DOMAIN
from homeassistant.components.dyson.sensor import SENSOR_ATTRIBUTES, SENSOR_NAMES
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM, UnitSystem

from .common import (
    BASE_PATH,
    CONFIG,
    ENTITY_NAME,
    NAME,
    SERIAL,
    async_update_device,
    get_basic_device,
)

from tests.common import async_setup_component

ENTITY_ID_PREFIX = f"{PLATFORM_DOMAIN}.{ENTITY_NAME}"

MOCKED_VALUES = {
    "filter_life": 100,
    "dust": 5,
    "humidity": 45,
    "temperature_kelvin": 295,
    "temperature": 21.9,
    "air_quality": 5,
    "hepa_filter_state": 50,
    "combi_filter_state": 50,
    "carbon_filter_state": 10,
}

MOCKED_UPDATED_VALUES = {
    "filter_life": 30,
    "dust": 2,
    "humidity": 80,
    "temperature_kelvin": 240,
    "temperature": -33.1,
    "air_quality": 3,
    "hepa_filter_state": 30,
    "combi_filter_state": 30,
    "carbon_filter_state": 20,
}


@callback
def _async_assign_values(
    device: DysonPureCoolLink, values=MOCKED_VALUES, combi=False
) -> None:
    """Assign mocked values to the device."""
    if isinstance(device, DysonPureCool):
        device.state.hepa_filter_state = values["hepa_filter_state"]
        device.state.carbon_filter_state = (
            "INV" if combi else values["carbon_filter_state"]
        )
        device.environmental_state.humidity = values["humidity"]
        device.environmental_state.temperature = values["temperature_kelvin"]
    else:  # DysonPureCoolLink
        device.state.filter_life = values["filter_life"]
        device.environmental_state.dust = values["dust"]
        device.environmental_state.humidity = values["humidity"]
        device.environmental_state.temperature = values["temperature_kelvin"]
        device.environmental_state.volatil_organic_compounds = values["air_quality"]


@callback
def async_get_device(spec: Type[DysonPureCoolLink], combi=False) -> DysonPureCoolLink:
    """Return a device of the given type."""
    device = get_basic_device(spec)
    _async_assign_values(device, combi=combi)
    return device


@callback
def _async_get_entity_id(sensor_type: str) -> str:
    """Get the expected entity id from the type of the sensor."""
    sensor_name = SENSOR_NAMES[sensor_type]
    entity_id_suffix = sensor_name.lower().replace(" ", "_")
    return f"{ENTITY_ID_PREFIX}_{entity_id_suffix}"


@pytest.mark.parametrize(
    "device,sensors",
    [
        (
            DysonPureCoolLink,
            ["filter_life", "dust", "humidity", "temperature", "air_quality"],
        ),
        (
            DysonPureCool,
            ["hepa_filter_state", "carbon_filter_state", "humidity", "temperature"],
        ),
        (
            [DysonPureCool, True],
            ["combi_filter_state", "humidity", "temperature"],
        ),
    ],
    indirect=["device"],
)
async def test_sensors(
    hass: HomeAssistant, device: DysonPureCoolLink, sensors: List[str]
) -> None:
    """Test the sensors."""
    # Temperature is given by the device in kelvin
    # Make sure no other sensors are set up
    assert len(hass.states.async_all()) == len(sensors)

    er = await entity_registry.async_get_registry(hass)
    for sensor in sensors:
        entity_id = _async_get_entity_id(sensor)

        # Test unique id
        assert er.async_get(entity_id).unique_id == f"{SERIAL}-{sensor}"

        # Test state
        state = hass.states.get(entity_id)
        assert state.state == str(MOCKED_VALUES[sensor])
        assert state.name == f"{NAME} {SENSOR_NAMES[sensor]}"

        # Test attributes
        attributes = state.attributes
        for attr, value in SENSOR_ATTRIBUTES[sensor].items():
            assert attributes[attr] == value

    # Test data update
    _async_assign_values(device, MOCKED_UPDATED_VALUES)
    await async_update_device(hass, device)
    for sensor in sensors:
        state = hass.states.get(_async_get_entity_id(sensor))
        assert state.state == str(MOCKED_UPDATED_VALUES[sensor])


@pytest.mark.parametrize("device", [DysonPureCoolLink], indirect=True)
async def test_sensors_off(hass: HomeAssistant, device: DysonPureCoolLink) -> None:
    """Test the case where temperature and humidity are not available."""
    device.environmental_state.temperature = 0
    device.environmental_state.humidity = 0
    await async_update_device(hass, device)
    assert hass.states.get(f"{ENTITY_ID_PREFIX}_temperature").state == STATE_OFF
    assert hass.states.get(f"{ENTITY_ID_PREFIX}_humidity").state == STATE_OFF


@pytest.mark.parametrize(
    "unit_system,temp_unit,temperature",
    [(METRIC_SYSTEM, TEMP_CELSIUS, 21.9), (IMPERIAL_SYSTEM, TEMP_FAHRENHEIT, 71.3)],
)
async def test_temperature(
    hass: HomeAssistant, unit_system: UnitSystem, temp_unit: str, temperature: float
) -> None:
    """Test the temperature sensor in different units."""
    hass.config.units = unit_system

    device = async_get_device(DysonPureCoolLink)
    with patch(f"{BASE_PATH}.DysonAccount.login", return_value=True), patch(
        f"{BASE_PATH}.DysonAccount.devices", return_value=[device]
    ), patch(f"{BASE_PATH}.DYSON_PLATFORMS", [PLATFORM_DOMAIN]):
        # DYSON_PLATFORMS is patched so that only the platform being tested is set up
        await async_setup_component(
            hass,
            DOMAIN,
            CONFIG,
        )
        await hass.async_block_till_done()

    state = hass.states.get(f"{ENTITY_ID_PREFIX}_temperature")
    assert state.state == str(temperature)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == temp_unit
