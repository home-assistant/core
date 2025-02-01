"""Test significant change helper."""

from types import MappingProxyType
from typing import Any

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import significant_change


@pytest.fixture(name="checker")
async def checker_fixture(
    hass: HomeAssistant,
) -> significant_change.SignificantlyChangedChecker:
    """Checker fixture."""
    checker = await significant_change.create_checker(hass, "test")

    def async_check_significant_change(
        _hass, old_state, _old_attrs, new_state, _new_attrs, **kwargs
    ):
        return abs(float(old_state) - float(new_state)) > 4

    hass.data[significant_change.DATA_FUNCTIONS]["test_domain"] = (
        async_check_significant_change
    )
    return checker


async def test_signicant_change(
    checker: significant_change.SignificantlyChangedChecker,
) -> None:
    """Test initialize helper works."""
    ent_id = "test_domain.test_entity"
    attrs = {ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY}

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


async def test_significant_change_extra(
    checker: significant_change.SignificantlyChangedChecker,
) -> None:
    """Test extra significant checker works."""
    ent_id = "test_domain.test_entity"
    attrs = {ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY}

    assert checker.async_is_significant_change(State(ent_id, "100", attrs), extra_arg=1)
    assert checker.async_is_significant_change(State(ent_id, "200", attrs), extra_arg=1)

    # Reset the last significiant change to 100 to repeat test but with
    # extra checker installed.
    assert checker.async_is_significant_change(State(ent_id, "100", attrs), extra_arg=1)

    def extra_significant_check(
        hass: HomeAssistant,
        old_state: str,
        old_attrs: dict | MappingProxyType,
        old_extra_arg: Any,
        new_state: str,
        new_attrs: dict | MappingProxyType,
        new_extra_arg: Any,
    ) -> bool | None:
        return old_extra_arg != new_extra_arg

    checker.extra_significant_check = extra_significant_check

    # This is normally a significant change (100 -> 200), but the extra arg check marks it
    # as insignificant.
    assert not checker.async_is_significant_change(
        State(ent_id, "200", attrs), extra_arg=1
    )
    assert checker.async_is_significant_change(State(ent_id, "200", attrs), extra_arg=2)


async def test_check_valid_float() -> None:
    """Test extra significant checker works."""
    assert significant_change.check_valid_float("1")
    assert significant_change.check_valid_float("1.0")
    assert significant_change.check_valid_float(1)
    assert significant_change.check_valid_float(1.0)
    assert not significant_change.check_valid_float("")
    assert not significant_change.check_valid_float("invalid")
    assert not significant_change.check_valid_float("1.1.1")
