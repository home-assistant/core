"""Tests for tracking setup-time trigger templates."""

from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger.template import async_track_trigger_template

from tests.common import MockConfigEntry, async_fire_time_changed

LEVEL_ENTITY_ID = "sensor.level"


async def test_static_template(hass: HomeAssistant) -> None:
    """Test a static template is rendered once and not tracked."""
    listeners_before = hass.bus.async_listeners()
    on_change = Mock()
    on_error = Mock()

    result, remove = async_track_trigger_template(
        hass, Template("some/topic", hass), None, on_change, on_error
    )

    assert result == "some/topic"
    assert hass.bus.async_listeners() == listeners_before

    remove()
    on_change.assert_not_called()
    on_error.assert_not_called()


async def test_initial_render_error_raises(hass: HomeAssistant) -> None:
    """Test a failing initial render raises and does not start tracking."""
    listeners_before = hass.bus.async_listeners()

    with pytest.raises(TemplateError):
        async_track_trigger_template(
            hass,
            Template("{{ states('sensor.level') | int }}", hass),
            None,
            Mock(),
            Mock(),
        )

    assert hass.bus.async_listeners() == listeners_before


@pytest.mark.parametrize(
    ("parse_result", "expected_initial", "expected_changed"),
    [(False, "3", "7"), (True, 3, 7)],
)
async def test_state_dependency(
    hass: HomeAssistant,
    parse_result: bool,
    expected_initial: str | int,
    expected_changed: str | int,
) -> None:
    """Test the result follows a state, but only reports actual changes."""
    hass.states.async_set(LEVEL_ENTITY_ID, "3")
    on_change = Mock()
    on_error = Mock()

    result, remove = async_track_trigger_template(
        hass,
        Template("{{ [states('sensor.level') | int, 7] | min }}", hass),
        None,
        on_change,
        on_error,
        parse_result=parse_result,
    )
    assert result == expected_initial

    hass.states.async_set(LEVEL_ENTITY_ID, "9")
    await hass.async_block_till_done()
    on_change.assert_called_once_with(expected_changed)

    # The state changes, but the rendered result stays the same.
    on_change.reset_mock()
    hass.states.async_set(LEVEL_ENTITY_ID, "12")
    await hass.async_block_till_done()
    on_change.assert_not_called()
    on_error.assert_not_called()

    remove()


async def test_variables(hass: HomeAssistant) -> None:
    """Test the variables are used for every render."""
    hass.states.async_set(LEVEL_ENTITY_ID, "3")
    on_change = Mock()

    result, remove = async_track_trigger_template(
        hass,
        Template("{{ prefix }}/{{ states('sensor.level') }}", hass),
        {"prefix": "home"},
        on_change,
        Mock(),
    )
    assert result == "home/3"

    hass.states.async_set(LEVEL_ENTITY_ID, "4")
    await hass.async_block_till_done()
    on_change.assert_called_once_with("home/4")

    remove()


async def test_registry_dependency(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device rename re-renders the template once, debounced."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "remote")},
        name="Kitchen remote",
    )
    on_change = Mock()
    on_error = Mock()

    result, remove = async_track_trigger_template(
        hass,
        Template("zigbee2mqtt/{{ device_attr(remote, 'name') }}/action", hass),
        {"remote": device.id},
        on_change,
        on_error,
    )
    assert result == "zigbee2mqtt/Kitchen remote/action"

    device_registry.async_update_device(device.id, name="Hallway remote")
    device_registry.async_update_device(device.id, name="Bedroom remote")
    await hass.async_block_till_done()
    on_change.assert_not_called()

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    on_change.assert_called_once_with("zigbee2mqtt/Bedroom remote/action")
    on_error.assert_not_called()

    remove()


async def test_error_keeps_last_result(hass: HomeAssistant) -> None:
    """Test a failing re-render reports the error and keeps the last result."""
    hass.states.async_set(LEVEL_ENTITY_ID, "3")
    on_change = Mock()
    on_error = Mock()

    _, remove = async_track_trigger_template(
        hass,
        Template("{{ states('sensor.level') | int }}", hass),
        None,
        on_change,
        on_error,
    )

    hass.states.async_set(LEVEL_ENTITY_ID, "unknown")
    await hass.async_block_till_done()
    on_error.assert_called_once()
    assert isinstance(on_error.call_args.args[0], TemplateError)
    on_change.assert_not_called()

    # Recovering to the last good result is not a change.
    hass.states.async_set(LEVEL_ENTITY_ID, "3")
    await hass.async_block_till_done()
    on_change.assert_not_called()

    hass.states.async_set(LEVEL_ENTITY_ID, "4")
    await hass.async_block_till_done()
    on_change.assert_called_once_with("4")

    remove()


async def test_remove_stops_tracking(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test removing stops tracking states and registries."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "remote")},
        name="Kitchen remote",
    )
    hass.states.async_set(LEVEL_ENTITY_ID, "3")
    listeners_before = hass.bus.async_listeners()
    on_change = Mock()

    _, remove = async_track_trigger_template(
        hass,
        Template(
            "{{ device_attr(remote, 'name') }}/{{ states('sensor.level') }}", hass
        ),
        {"remote": device.id},
        on_change,
        Mock(),
    )
    assert hass.bus.async_listeners() != listeners_before

    # A registry update is pending when tracking stops.
    device_registry.async_update_device(device.id, name="Hallway remote")
    remove()
    assert hass.bus.async_listeners() == listeners_before

    hass.states.async_set(LEVEL_ENTITY_ID, "4")
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    on_change.assert_not_called()
