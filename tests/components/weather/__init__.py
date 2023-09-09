"""The tests for Weather platforms."""


from homeassistant.components.weather import ATTR_CONDITION_SUNNY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.testing_config.custom_components.test import weather as WeatherPlatform


async def create_entity(hass: HomeAssistant, **kwargs):
    """Create the weather entity to run tests on."""
    kwargs = {
        "native_temperature": None,
        "native_temperature_unit": None,
        "is_daytime": True,
        **kwargs,
    }
    platform: WeatherPlatform = getattr(hass.components, "test.weather")
    platform.init(empty=True)
    platform.ENTITIES.append(
        platform.MockWeatherMockForecast(
            name="Test", condition=ATTR_CONDITION_SUNNY, **kwargs
        )
    )

    entity0 = platform.ENTITIES[0]
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )
    await hass.async_block_till_done()
    return entity0
