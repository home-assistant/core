"""Test air_quality of Airly integration."""
from datetime import timedelta
import json

from airly.exceptions import AirlyError

from homeassistant.components.air_quality import ATTR_AQI, ATTR_PM_2_5, ATTR_PM_10
from homeassistant.components.airly.air_quality import (
    ATTRIBUTION,
    LABEL_ADVICE,
    LABEL_AQI_DESCRIPTION,
    LABEL_AQI_LEVEL,
    LABEL_PM_2_5_LIMIT,
    LABEL_PM_2_5_PERCENT,
    LABEL_PM_10_LIMIT,
    LABEL_PM_10_PERCENT,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.async_mock import patch
from tests.common import async_fire_time_changed, load_fixture
from tests.components.airly import init_integration


async def test_air_quality(hass):
    """Test states of the air_quality."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("air_quality.home")
    assert state
    assert state.state == "14"
    assert state.attributes.get(ATTR_AQI) == 23
    assert state.attributes.get(ATTR_ATTRIBUTION) == ATTRIBUTION
    assert state.attributes.get(LABEL_ADVICE) == "Great air!"
    assert state.attributes.get(ATTR_PM_10) == 19
    assert state.attributes.get(ATTR_PM_2_5) == 14
    assert state.attributes.get(LABEL_AQI_DESCRIPTION) == "Great air here today!"
    assert state.attributes.get(LABEL_AQI_LEVEL) == "very low"
    assert state.attributes.get(LABEL_PM_2_5_LIMIT) == 25.0
    assert state.attributes.get(LABEL_PM_2_5_PERCENT) == 55
    assert state.attributes.get(LABEL_PM_10_LIMIT) == 50.0
    assert state.attributes.get(LABEL_PM_10_PERCENT) == 37
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert state.attributes.get(ATTR_ICON) == "mdi:blur"

    entry = registry.async_get("air_quality.home")
    assert entry
    assert entry.unique_id == "55.55-122.12"


async def test_availability(hass):
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    await init_integration(hass)

    state = hass.states.get("air_quality.home")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14"

    future = utcnow() + timedelta(minutes=60)
    with patch(
        "airly._private._RequestsHandler.get",
        side_effect=AirlyError(500, "Unexpected error"),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("air_quality.home")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=120)
    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("air_quality.home")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "14"


async def test_manual_update_entity(hass):
    """Test manual update entity via service homeasasistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})
    with patch(
        "homeassistant.components.airly.AirlyDataUpdateCoordinator._async_update_data"
    ) as mock_update:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["air_quality.home"]},
            blocking=True,
        )
        assert mock_update.call_count == 1
