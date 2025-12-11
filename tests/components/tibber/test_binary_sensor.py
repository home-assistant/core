from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from homeassistant.components.tibber.binary_sensor import (
    DEFAULT_THRESHOLD,
    SCAN_INTERVAL,
    SERVICE_SET_THRESHOLD,
    TibberPhaseImbalanceAlarmBinarySensor,
)


def _fake_home(home_id: str = "home-id-1", name: str = "Test Home"):
    """Return a minimal TibberHome-like object."""
    return SimpleNamespace(home_id=home_id, name=name)


# --------------------------------------------------------------------
# Constant verification
# --------------------------------------------------------------------


async def test_constants_defined() -> None:
    """Verify module-level constants are correct."""
    assert DEFAULT_THRESHOLD == 20.0
    assert isinstance(SCAN_INTERVAL, timedelta)
    assert SCAN_INTERVAL.total_seconds() == 30
    assert SERVICE_SET_THRESHOLD == "set_phase_imbalance_threshold"


# --------------------------------------------------------------------
# Class structure and initialization behavior
# --------------------------------------------------------------------


async def test_binary_sensor_class_structure() -> None:
    """Verify the class exposes required attributes/methods."""
    cls = TibberPhaseImbalanceAlarmBinarySensor
    assert hasattr(cls, "_attr_device_class")
    assert hasattr(cls, "_attr_translation_key")
    assert hasattr(cls, "set_threshold")
    assert hasattr(cls, "async_update")
    assert hasattr(cls, "device_info")


async def test_init_assigns_expected_attributes(hass: HomeAssistant) -> None:
    """Verify initial unique_id, device_info, and extra state attributes."""
    home = _fake_home()
    source = "sensor.phase_imbalance_percent"

    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, source)
    sensor.hass = hass

    # unique_id
    assert sensor.unique_id == f"{home.home_id}_rt_phase_imbalance_alarm"

    # extra attributes
    attrs = sensor.extra_state_attributes
    assert attrs["threshold_percent"] == DEFAULT_THRESHOLD
    assert attrs["phase_imbalance_percent"] is None
    assert attrs["source_entity_id"] == source

    # device_info
    info = sensor.device_info
    assert info["identifiers"] == {("tibber", home.home_id)}
    assert info["name"] == home.name
    assert info["model"] == "Tibber Pulse"
    assert info["manufacturer"] == "Tibber"


# --------------------------------------------------------------------
# Threshold updates
# --------------------------------------------------------------------


async def test_set_threshold_changes_value(hass: HomeAssistant) -> None:
    """set_threshold should update both internal and exposed values."""
    home = _fake_home()
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, "sensor.phase")
    sensor.hass = hass

    sensor.set_threshold(35.0)
    assert sensor.extra_state_attributes["threshold_percent"] == 35.0

    sensor.set_threshold(10.0)
    assert sensor.extra_state_attributes["threshold_percent"] == 10.0


# --------------------------------------------------------------------
# async_update: source entity is known
# --------------------------------------------------------------------


async def test_update_off_when_below_threshold(hass: HomeAssistant) -> None:
    """Value < threshold should set is_on = False."""
    home = _fake_home()
    src = "sensor.phase"
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, src)
    sensor.hass = hass

    hass.states.async_set(src, "10.0")
    await hass.async_block_till_done()

    await sensor.async_update()

    assert sensor.is_on is False
    assert sensor.extra_state_attributes["phase_imbalance_percent"] == 10.0


async def test_update_on_when_above_threshold(hass: HomeAssistant) -> None:
    """Value > threshold should set is_on = True."""
    home = _fake_home()
    src = "sensor.phase"
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, src)
    sensor.hass = hass

    hass.states.async_set(src, "25.0")
    await hass.async_block_till_done()

    await sensor.async_update()

    assert sensor.is_on is True
    assert sensor.extra_state_attributes["phase_imbalance_percent"] == 25.0


async def test_update_handles_non_numeric(hass: HomeAssistant) -> None:
    """Non-numeric state should keep alarm off and clear the value."""
    home = _fake_home()
    src = "sensor.phase"
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, src)
    sensor.hass = hass

    hass.states.async_set(src, "unknown")
    await hass.async_block_till_done()

    await sensor.async_update()

    assert sensor.is_on is False
    assert sensor.extra_state_attributes["phase_imbalance_percent"] is None


async def test_update_handles_missing_state(hass: HomeAssistant) -> None:
    """Missing state object should result in safe fallback."""
    home = _fake_home()
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, "sensor.missing")
    sensor.hass = hass

    await sensor.async_update()

    assert sensor.is_on is False
    assert sensor.extra_state_attributes["phase_imbalance_percent"] is None


# --------------------------------------------------------------------
# async_update: source_entity_id is None → entity_registry lookup
# --------------------------------------------------------------------


async def test_update_resolves_source_entity_id_from_registry(
    hass: HomeAssistant,
) -> None:
    """Sensor should fetch source_entity_id from entity registry if None."""
    home = _fake_home()
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, None)
    sensor.hass = hass

    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        domain="sensor",
        platform="tibber",
        unique_id=f"{home.home_id}_rt_phase_imbalance_percent",
        suggested_object_id="phase_imbalance_percent",
    )

    hass.states.async_set(entry.entity_id, "30.0")
    await hass.async_block_till_done()

    await sensor.async_update()

    assert sensor.is_on is True
    assert sensor.extra_state_attributes["source_entity_id"] == entry.entity_id
    assert sensor.extra_state_attributes["phase_imbalance_percent"] == 30.0


async def test_update_no_matching_source_in_registry(
    hass: HomeAssistant,
) -> None:
    """If no entity matches the lookup, alarm remains off."""
    home = _fake_home()
    sensor = TibberPhaseImbalanceAlarmBinarySensor(home, None)
    sensor.hass = hass

    await sensor.async_update()

    assert sensor.is_on is False
    assert sensor.extra_state_attributes["source_entity_id"] is None
    assert sensor.extra_state_attributes["phase_imbalance_percent"] is None
