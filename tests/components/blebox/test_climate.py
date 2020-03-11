"""BleBox climate entities tests."""

from asynctest import CoroutineMock
import blebox_uniapi
import pytest

from homeassistant.components.blebox import climate
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .conftest import DefaultBoxTest, mock_feature


@pytest.fixture
def feature_mock():
    """Return a mocked Climate feature."""
    return mock_feature(
        "climates",
        blebox_uniapi.feature.Climate,
        unique_id="BleBox-saunaBox-1afe34db9437-thermostat",
        full_name="saunaBox-thermostat",
        device_class=None,
        is_on=None,
        desired=None,
        current=None,
    )


@pytest.fixture
def updateable_feature_mock(feature_mock):
    """Set up mocked feature that can be updated."""

    def update():
        feature_mock.is_on = False
        feature_mock.desired = 64.3
        feature_mock.current = 40.9

    feature_mock.async_update = CoroutineMock(side_effect=update)
    return feature_mock


@pytest.fixture
def off_to_heat_feature_mock(feature_mock):
    """Set up mocked feature that can be updated and turned on."""

    def update():
        feature_mock.is_on = False

    def turn_on():
        feature_mock.is_on = True
        feature_mock.is_heating = True
        feature_mock.desired = 64.8
        feature_mock.current = 25.7

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_on = CoroutineMock(side_effect=turn_on)
    return feature_mock


@pytest.fixture
def off_to_idle_feature_mock(feature_mock):
    """Set up mocked feature that can be updated and turned on."""

    def update():
        feature_mock.is_on = False

    def turn_on():
        feature_mock.is_on = True
        feature_mock.is_heating = False
        feature_mock.desired = 23.4
        feature_mock.current = 28.7

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_on = CoroutineMock(side_effect=turn_on)
    return feature_mock


@pytest.fixture
def idle_to_off_feature_mock(feature_mock):
    """Set up mocked feature that can be updated and turned off."""

    def update():
        feature_mock.is_on = True
        feature_mock.is_heating = False

    def turn_off():
        feature_mock.is_on = False
        feature_mock.is_heating = False
        feature_mock.desired = 29.8
        feature_mock.current = 22.7

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_off = CoroutineMock(side_effect=turn_off)
    return feature_mock


@pytest.fixture
def on_via_set_feature_mock(feature_mock):
    """Set up mocked feature that can be updated and controlled."""

    def update():
        feature_mock.is_on = False
        feature_mock.is_heating = False

    def set_temp(temp):
        feature_mock.is_on = True
        feature_mock.is_heating = True
        feature_mock.desired = 29.2
        feature_mock.current = 29.1

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_set_temperature = CoroutineMock(side_effect=set_temp)

    return feature_mock


class TestSauna(DefaultBoxTest):
    """Tests for entities representing a BleBox saunaBox."""

    HASS_TYPE = climate

    async def test_init(self, hass, feature_mock):
        """Test default state."""

        entity = (await self.async_entities(hass))[0]

        assert entity.name == "saunaBox-thermostat"
        assert entity.unique_id == "BleBox-saunaBox-1afe34db9437-thermostat"

        assert entity.device_class is None
        assert entity.supported_features & SUPPORT_TARGET_TEMPERATURE
        assert entity.hvac_modes == (HVAC_MODE_OFF, HVAC_MODE_HEAT)

        assert entity.hvac_mode is None
        assert entity.hvac_action is None
        assert entity.target_temperature is None
        assert entity.current_temperature is None
        assert entity.temperature_unit == TEMP_CELSIUS
        assert entity.state is None

    async def test_update(self, hass, updateable_feature_mock):
        """Test updating."""

        entity = await self.async_updated_entity(hass, 0)

        assert entity.hvac_mode == HVAC_MODE_OFF
        assert entity.hvac_action == CURRENT_HVAC_OFF
        assert entity.target_temperature == 64.3
        assert entity.current_temperature == 40.9
        assert entity.temperature_unit == TEMP_CELSIUS

    async def test_on_when_below_desired(self, hass, off_to_heat_feature_mock):
        """Test when temperature is below desired."""

        entity = await self.async_updated_entity(hass, 0)
        await entity.async_set_hvac_mode(HVAC_MODE_HEAT)

        assert entity.state == entity.hvac_mode == HVAC_MODE_HEAT
        assert entity.target_temperature == 64.8
        assert entity.current_temperature == 25.7
        assert entity.hvac_action == CURRENT_HVAC_HEAT

    async def test_on_when_above_desired(self, hass, off_to_idle_feature_mock):
        """Test when temperature is below desired."""

        entity = await self.async_updated_entity(hass, 0)
        await entity.async_set_hvac_mode(HVAC_MODE_HEAT)

        assert entity.target_temperature == 23.4
        assert entity.current_temperature == 28.7
        assert entity.state == entity.hvac_mode == HVAC_MODE_HEAT
        assert entity.hvac_action == CURRENT_HVAC_IDLE

    async def test_off(self, hass, idle_to_off_feature_mock):
        """Test turning off."""

        entity = await self.async_updated_entity(hass, 0)
        await entity.async_set_hvac_mode(HVAC_MODE_OFF)

        assert entity.target_temperature == 29.8
        assert entity.current_temperature == 22.7
        assert entity.state == entity.hvac_mode == HVAC_MODE_OFF
        assert entity.hvac_action == CURRENT_HVAC_OFF

    async def test_set_thermo(self, hass, on_via_set_feature_mock):
        """Test setting thermostat."""

        entity = await self.async_updated_entity(hass, 0)
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 43.21})

        assert entity.target_temperature == 29.2
        assert entity.current_temperature == 29.1
        assert entity.state == entity.hvac_mode == HVAC_MODE_HEAT
        assert entity.hvac_action == CURRENT_HVAC_HEAT
