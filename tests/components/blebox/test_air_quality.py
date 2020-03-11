"""Blebox air_quality tests."""

from asynctest import CoroutineMock
import blebox_uniapi
import pytest

from homeassistant.components.blebox import air_quality

from .conftest import DefaultBoxTest, mock_feature


@pytest.fixture
def feature_mock():
    """Return a mocked Air Quality feature."""
    return mock_feature(
        "air_qualities",
        blebox_uniapi.feature.AirQuality,
        unique_id="BleBox-airSensor-1afe34db9437-0.air",
        full_name="airSensor-0.air",
        device_class=None,
        pm1=None,
        pm2_5=None,
        pm10=None,
    )


@pytest.fixture
def updateable_feature_mock(feature_mock):
    """Set up mocked feature that can be updated."""

    def update():
        feature_mock.pm1 = 49
        feature_mock.pm2_5 = 222
        feature_mock.pm10 = 333

    feature_mock.async_update = CoroutineMock(side_effect=update)


class TestAirSensor(DefaultBoxTest):
    """Tests for sensors representing BleBox airSensor."""

    HASS_TYPE = air_quality

    async def test_init(self, hass, feature_mock):
        """Test air quality sensor default state."""

        entity = (await self.async_entities(hass))[0]

        assert entity.name == "airSensor-0.air"
        assert entity.icon == "mdi:blur"
        assert entity.unique_id == "BleBox-airSensor-1afe34db9437-0.air"
        assert entity.particulate_matter_0_1 is None
        assert entity.particulate_matter_2_5 is None
        assert entity.particulate_matter_10 is None

    async def test_update(self, hass, updateable_feature_mock):
        """Test air quality sensor state after update."""

        entity = (await self.async_entities(hass))[0]

        await entity.async_update()

        assert entity.particulate_matter_0_1 == 49
        assert entity.particulate_matter_2_5 == 222
        assert entity.particulate_matter_10 == 333
