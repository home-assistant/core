"""The tests for cover recorder."""

from datetime import timedelta

from pytest_homeassistant.common import (
    async_fire_time_changed,
    setup_test_component_platform,
)
from pytest_homeassistant.components.recorder.common import async_wait_recording_done

from homeassistant.components.cover import (
    DOMAIN,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverEntityStateAttribute,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import MockCover

UNRECORDED_ATTRIBUTES = (
    CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS,
    CoverEntityCapabilityAttribute.OPEN_TILT_POSITION,
    CoverEntityCapabilityAttribute.CLOSED_TILT_POSITIONS,
    CoverEntityCapabilityAttribute.TILT_START_ANGLE,
    CoverEntityCapabilityAttribute.TILT_END_ANGLE,
)


async def test_exclude_attributes(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test cover attributes to be excluded."""
    now = dt_util.utcnow()
    setup_test_component_platform(
        hass,
        DOMAIN,
        [
            MockCover(
                name="Tilt cover",
                unique_id="tilt_cover",
                current_cover_tilt_position=30,
                supported_speeds=["slow", "fast"],
                tilt_start_angle=-90,
                tilt_end_angle=90,
                supported_features=CoverEntityFeature.SET_TILT_POSITION,
            )
        ],
    )
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()
    state = hass.states.get("cover.tilt_cover")
    assert state is not None
    for attribute in UNRECORDED_ATTRIBUTES:
        assert attribute in state.attributes

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        get_significant_states, hass, now, None, hass.states.async_entity_ids()
    )
    assert len(states) == 1
    for entity_states in states.values():
        for state in entity_states:
            for attribute in UNRECORDED_ATTRIBUTES:
                assert attribute not in state.attributes
            assert (
                state.attributes[CoverEntityStateAttribute.CURRENT_TILT_POSITION] == 30
            )
