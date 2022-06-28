"""Test sensor of NextDNS integration."""
from homeassistant.components.nextdns.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorStateClass,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_sensor(hass):
    """Test states of sensors."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "xyz12_doh_queries",
        suggested_object_id="fake_profile_doh_queries",
        disabled_by=None,
    )

    await init_integration(hass)

    state = hass.states.get("sensor.fake_profile_doh_queries")
    assert state
    assert state.state == "20"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "queries"

    entry = registry.async_get("sensor.fake_profile_doh_queries")
    assert entry
    assert entry.unique_id == "xyz12_doh_queries"
