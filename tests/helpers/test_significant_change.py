"""Test significant change helper."""
import pytest

from homeassistant.components.sensor import DEVICE_CLASS_BATTERY
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State
from homeassistant.helpers import significant_change
from homeassistant.setup import async_setup_component


@pytest.fixture(name="checker")
async def checker_fixture(hass):
    """Checker fixture."""
    checker = await significant_change.create_checker(hass, "test")

    def async_check_significant_change(
        _hass, old_state, _old_attrs, new_state, _new_attrs, **kwargs
    ):
        return abs(float(old_state) - float(new_state)) > 4

    hass.data[significant_change.DATA_FUNCTIONS][
        "test_domain"
    ] = async_check_significant_change
    return checker


async def test_signicant_change(hass, checker):
    """Test initialize helper works."""
    assert await async_setup_component(hass, "sensor", {})

    ent_id = "test_domain.test_entity"
    attrs = {ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY}

    assert checker.async_is_significant_change(State(ent_id, "100", attrs))

    # Same state is not significant.
    assert not checker.async_is_significant_change(State(ent_id, "100", attrs))

    # State under 5 difference is not significant. (per test mock)
    assert not checker.async_is_significant_change(State(ent_id, "96", attrs))

    # Make sure we always compare against last significant change
    assert checker.async_is_significant_change(State(ent_id, "95", attrs))

    # State turned unknown
    assert checker.async_is_significant_change(State(ent_id, STATE_UNKNOWN, attrs))

    # State turned unavailable
    assert checker.async_is_significant_change(State(ent_id, "100", attrs))
    assert checker.async_is_significant_change(State(ent_id, STATE_UNAVAILABLE, attrs))
