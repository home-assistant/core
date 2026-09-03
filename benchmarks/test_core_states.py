"""CodSpeed benchmarks for the state machine and entity write path.

Every state update in Home Assistant flows through ``StateMachine.async_set``,
and every entity that pushes an update lands in ``Entity._async_write_ha_state``.
These are among the busiest call sites in the whole process.

Run locally with: ``pytest benchmarks --codspeed``.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pytest_codspeed import BenchmarkFixture

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity import Entity

_ATTRS = {
    "friendly_name": "Benchmark light",
    "brightness": 255,
    "color_temp_kelvin": 4000,
    "supported_color_modes": ["color_temp", "rgb"],
}


def test_state_set_create(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Write a brand new entity into the state machine (the create branch).

    ``pedantic`` with a teardown that removes the entity keeps every measured
    call on the create path; without it only the first call creates and the rest
    measure the update path.
    """
    benchmark.pedantic(
        lambda: hass.states.async_set("light.benchmark", "on", _ATTRS),
        teardown=lambda: hass.states.async_remove("light.benchmark"),
        rounds=1000,
    )


def test_state_set_update(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Write a changed state for an existing entity (the update branch)."""
    counter = 0

    def _set() -> None:
        nonlocal counter
        counter += 1
        hass.states.async_set("light.benchmark", str(counter), _ATTRS)

    benchmark(_set)

    assert hass.states.get("light.benchmark") is not None


def test_state_set_report(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Re-set an unchanged state (the EVENT_STATE_REPORTED fast path).

    Polling integrations hammer this branch: same value, same attributes, over
    and over. It fires a lightweight reported event instead of a state change.
    """
    hass.states.async_set("sensor.benchmark", "21.5", _ATTRS)

    benchmark(lambda: hass.states.async_set("sensor.benchmark", "21.5", _ATTRS))


def test_state_get(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Look a single state up by entity_id."""
    hass.states.async_set("sensor.benchmark", "21.5", _ATTRS)

    state: State | None = benchmark(lambda: hass.states.get("sensor.benchmark"))

    assert state is not None
    assert state.state == "21.5"


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_state_all(
    benchmark: BenchmarkFixture,
    populate_states: Callable[[int], None],
    hass: HomeAssistant,
    count: int,
) -> None:
    """Read the full state list out of a populated machine, at several sizes."""
    populate_states(count)

    states: list[State] = benchmark(hass.states.async_all)

    assert len(states) == count


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_state_entity_ids(
    benchmark: BenchmarkFixture,
    populate_states: Callable[[int], None],
    hass: HomeAssistant,
    count: int,
) -> None:
    """List entity ids out of a populated machine, at several sizes."""
    populate_states(count)

    entity_ids = benchmark(hass.states.async_entity_ids)

    assert len(entity_ids) == count


class _BenchmarkEntity(Entity):
    """A minimal entity carrying capability and extra state attributes."""

    _attr_should_poll = False
    _attr_name = "Benchmark"
    _attr_supported_features = 3

    def __init__(self, state: str) -> None:
        """Initialize the benchmark entity."""
        self._attr_state = state
        self._attr_extra_state_attributes: dict[str, Any] = {
            "brightness": 255,
            "color_temp_kelvin": 4000,
        }

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes, assembled on every write."""
        return {"supported_color_modes": ["color_temp", "rgb"]}


def test_entity_write(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Write an entity's state through the entity layer.

    This measures ``__async_calculate_state`` (assembling state and attributes
    from the entity's properties) plus the ``async_set`` it lands in.
    """
    entity = _BenchmarkEntity("on")
    entity.hass = hass
    entity.entity_id = "light.benchmark"

    benchmark(entity._async_write_ha_state)  # noqa: SLF001

    assert hass.states.get("light.benchmark") is not None
