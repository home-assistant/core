"""Blebox sensors tests."""

from asynctest import CoroutineMock
import blebox_uniapi
import pytest

from homeassistant.components.blebox import sensor
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS

from .conftest import DefaultBoxTest, mock_feature


class TestTempSensor(DefaultBoxTest):
    """Tests for sensors representing BleBox tempSensor."""

    HASS_TYPE = sensor

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Sensor feature representing a tempSensor."""
        self._feature_mock = mock_feature(
            "sensors",
            blebox_uniapi.feature.Temperature,
            unique_id="BleBox-tempSensor-1afe34db9437-0.temperature",
            full_name="tempSensor-0.temperature",
            device_class="temperature",
            unit="celsius",
            current=None,
        )
        return self._feature_mock

    async def test_init(self, hass):
        """Test sensor default state."""

        entity = (await self.async_entities(hass))[0]

        # TODO: include user-specified device name here too
        # TODO: maybe blebox_uniapi shouldn't generate name at all?
        assert entity.name == "tempSensor-0.temperature"

        assert entity.device_class == DEVICE_CLASS_TEMPERATURE
        assert entity.unique_id == "BleBox-tempSensor-1afe34db9437-0.temperature"
        assert entity.unit_of_measurement == TEMP_CELSIUS
        assert entity.state is None

    def updateable_feature_mock(self):
        """Set up mocked feature that can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.current = 25.18

        feature_mock.async_update = CoroutineMock(side_effect=update)

    async def test_update(self, hass):
        """Test sensor update."""
        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        assert entity.state == 25.18
