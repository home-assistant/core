"""Sensors for National Weather Service (NWS)."""
import pytest

from homeassistant.components.nws.const import ATTRIBUTION, DOMAIN, SENSOR_TYPES
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.common import MockConfigEntry
from tests.components.nws.const import (
    EXPECTED_FORECAST_IMPERIAL,
    EXPECTED_FORECAST_METRIC,
    NONE_OBSERVATION,
    NWS_CONFIG,
    SENSOR_EXPECTED_OBSERVATION_IMPERIAL,
    SENSOR_EXPECTED_OBSERVATION_METRIC,
)


@pytest.mark.parametrize(
    "units,result_observation,result_forecast",
    [
        (
            IMPERIAL_SYSTEM,
            SENSOR_EXPECTED_OBSERVATION_IMPERIAL,
            EXPECTED_FORECAST_IMPERIAL,
        ),
        (METRIC_SYSTEM, SENSOR_EXPECTED_OBSERVATION_METRIC, EXPECTED_FORECAST_METRIC),
    ],
)
async def test_imperial_metric(
    hass, units, result_observation, result_forecast, mock_simple_nws, no_weather
):
    """Test with imperial and metric units."""
    registry = er.async_get(hass)

    for description in SENSOR_TYPES:
        registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            f"35_-75_{description.key}",
            suggested_object_id=f"abc_{description.name}",
            disabled_by=None,
        )

    hass.config.units = units
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for description in SENSOR_TYPES:
        assert description.name
        state = hass.states.get(f"sensor.abc_{slugify(description.name)}")
        assert state
        assert state.state == result_observation[description.key]
        assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION


async def test_none_values(hass, mock_simple_nws, no_weather):
    """Test with no values."""
    instance = mock_simple_nws.return_value
    instance.observation = NONE_OBSERVATION

    registry = er.async_get(hass)

    for description in SENSOR_TYPES:
        registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            f"35_-75_{description.key}",
            suggested_object_id=f"abc_{description.name}",
            disabled_by=None,
        )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for description in SENSOR_TYPES:
        assert description.name
        state = hass.states.get(f"sensor.abc_{slugify(description.name)}")
        assert state
        assert state.state == STATE_UNKNOWN
