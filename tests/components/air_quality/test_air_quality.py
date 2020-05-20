"""The tests for the Air Quality component."""
from homeassistant.components.air_quality import (
    ATTR_ATTRIBUTION,
    ATTR_N2O,
    ATTR_OZONE,
    ATTR_PM_10,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
)
from homeassistant.setup import async_setup_component


async def test_state(hass):
    """Test Air Quality state."""
    config = {"air_quality": {"platform": "demo"}}

    assert await async_setup_component(hass, "air_quality", config)

    state = hass.states.get("air_quality.demo_air_quality_home")
    assert state is not None

    assert state.state == "14"


async def test_attributes(hass):
    """Test Air Quality attributes."""
    config = {"air_quality": {"platform": "demo"}}

    assert await async_setup_component(hass, "air_quality", config)

    state = hass.states.get("air_quality.demo_air_quality_office")
    assert state is not None

    data = state.attributes
    assert data.get(ATTR_PM_10) == 16
    assert data.get(ATTR_N2O) is None
    assert data.get(ATTR_OZONE) is None
    assert data.get(ATTR_ATTRIBUTION) == "Powered by Home Assistant"
    assert (
        data.get(ATTR_UNIT_OF_MEASUREMENT) == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
