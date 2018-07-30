"""The tests for the Demo sous-vide platform."""
from unittest.mock import MagicMock

import pytest
from homeassistant.components import climate, sous_vide
from homeassistant.components.sous_vide import demo
from homeassistant.components.sous_vide.demo import DemoSousVideEntity
from homeassistant.const import (
    ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT, STATE_OFF, TEMP_CELSIUS)
from homeassistant.helpers.temperature import display_temp
from homeassistant.setup import setup_component
from homeassistant.util import temperature
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM
from tests.common import assert_setup_component, get_test_home_assistant

DEMO_ENTITY_ID = "{}.{}".format(sous_vide.DOMAIN, demo.DEMO_ENTITY_NAME)


@pytest.fixture(scope="module",
                params=[IMPERIAL_SYSTEM, METRIC_SYSTEM])
def mock_hass(request):
    """Create a mock homeassistant for unit testing."""
    # TODO: This introduces extra coupling to the implementation details of
    # HomeAssistant, Config, and Units.  Refactor display_temp to to a Units
    # to fix this.
    converting_hass = MagicMock()
    converting_hass.config = MagicMock()
    converting_hass.config.units = request.param
    return converting_hass


@pytest.fixture(scope="module",
                params=[IMPERIAL_SYSTEM, METRIC_SYSTEM])
def hass(request):
    """Create a homeassistant for integration testing."""
    hass_obj = get_test_home_assistant()
    hass_obj.config.units = request.param
    request.addfinalizer(hass_obj.stop)
    return hass_obj


@pytest.fixture(scope="module",
                params=[IMPERIAL_SYSTEM, METRIC_SYSTEM])
def demo_entity(request, mock_hass):
    """Create a demo sous-vide entity for testing."""
    entity = DemoSousVideEntity(name=demo.DEMO_ENTITY_NAME,
                                unit=request.param.temperature_unit)
    entity.hass = mock_hass  # Entity uses internally for conversions.

    return entity


@pytest.fixture
def component_setup(hass):
    """Initialize a demo sous-vide platform."""
    with assert_setup_component(1):
        assert setup_component(hass, sous_vide.DOMAIN, {
            sous_vide.DOMAIN: {
                'platform': 'demo'
            }
        })


def test_default_state(demo_entity):
    """Test setup_platform with the default state."""
    assert demo_entity
    assert demo_entity.name == demo.DEMO_ENTITY_NAME
    assert demo_entity.state == STATE_OFF
    assert not demo_entity.is_on

    # Test is paramtetized by these.
    assert demo_entity.unit_of_measurement == \
        demo_entity.state_attributes[ATTR_UNIT_OF_MEASUREMENT]
    assert demo_entity.precision == \
        demo_entity.state_attributes[sous_vide.ATTR_MEASUREMENT_PRECISION]

    # Test conversions.
    assert demo_entity.min_temperature == temperature.convert(
        demo.DEFAULT_MIN_TEMP_IN_C, TEMP_CELSIUS,
        demo_entity.unit_of_measurement)
    assert demo_entity.state_attributes[climate.ATTR_MIN_TEMP] == \
        demo_entity.convert_to_display_temp(demo_entity.min_temperature)
    assert demo_entity.max_temperature == temperature.convert(
        demo.DEFAULT_MAX_TEMP_IN_C, TEMP_CELSIUS,
        demo_entity.unit_of_measurement)
    assert demo_entity.state_attributes[climate.ATTR_MAX_TEMP] == \
        demo_entity.convert_to_display_temp(demo_entity.max_temperature)
    assert demo_entity.current_temperature == temperature.convert(
        demo.DEFAULT_CURRENT_TEMP_IN_C, TEMP_CELSIUS,
        demo_entity.unit_of_measurement)
    assert demo_entity.state_attributes[climate.ATTR_CURRENT_TEMPERATURE] == \
        demo_entity.convert_to_display_temp(demo_entity.current_temperature)
    assert demo_entity.target_temperature == temperature.convert(
        demo.DEFAULT_TARGET_TEMP_IN_C, TEMP_CELSIUS,
        demo_entity.unit_of_measurement)
    assert demo_entity.state_attributes[ATTR_TEMPERATURE] == \
        demo_entity.convert_to_display_temp(demo_entity.target_temperature)


def test_setup_platform_default_state(hass, component_setup):
    """Test setup_platform with the default state."""
    demo_entity_state = hass.states.get(DEMO_ENTITY_ID)
    assert demo_entity_state is not None
    assert demo_entity_state.name == demo.DEMO_ENTITY_NAME
    assert demo_entity_state.state == STATE_OFF

    # Test is parameterized by these.
    demo_entity_unit = \
        demo_entity_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
    demo_entity_precision = \
        demo_entity_state.attributes[sous_vide.ATTR_MEASUREMENT_PRECISION]
    assert demo_entity_unit == demo.DEFAULT_UNIT
    assert demo_entity_precision == demo.DEFAULT_PRECISION

    # Test conversions.
    assert demo_entity_state.attributes[climate.ATTR_MIN_TEMP] == \
        display_temp(hass, demo.DEFAULT_MIN_TEMP_IN_C,
                     demo_entity_unit, demo_entity_precision)
    assert demo_entity_state.attributes[climate.ATTR_MAX_TEMP] == \
        display_temp(hass, demo.DEFAULT_MAX_TEMP_IN_C,
                     demo_entity_unit, demo_entity_precision)
    assert demo_entity_state.attributes[climate.ATTR_CURRENT_TEMPERATURE] == \
        display_temp(hass, demo.DEFAULT_CURRENT_TEMP_IN_C,
                     demo_entity_unit, demo_entity_precision)
    assert demo_entity_state.attributes[climate.ATTR_TEMPERATURE] == \
        display_temp(hass, demo.DEFAULT_TARGET_TEMP_IN_C,
                     demo_entity_unit, demo_entity_precision)
