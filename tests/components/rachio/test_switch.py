"""Tests for the Rachio switch platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.rachio.const import (
    KEY_ENABLED,
    KEY_ID,
    KEY_NAME,
    KEY_ZONE_NUMBER,
)
from homeassistant.components.rachio.switch import RachioZone


def _create_zone() -> tuple[RachioZone, MagicMock]:
    """Create a Rachio zone for testing."""
    person = MagicMock()
    person.config_entry.options = {}

    controller = MagicMock()
    controller.controller_id = "controller-id"
    controller.serial_number = "serial-number"
    controller.mac_address = "00:9D:6B:00:00:01"
    controller.name = "Test Controller"
    controller.model = "GENERATION3"

    zone = RachioZone(
        person,
        controller,
        {
            KEY_ID: "zone-id",
            KEY_NAME: "Test Zone",
            KEY_ZONE_NUMBER: 1,
            KEY_ENABLED: True,
        },
        {},
    )
    zone.schedule_update_ha_state = MagicMock()
    return zone, controller


def test_zone_turn_on_updates_state() -> None:
    """Test starting a zone optimistically updates its state."""
    zone, controller = _create_zone()

    zone.turn_on()

    controller.stop_watering.assert_called_once_with()
    controller.rachio.zone.start.assert_called_once_with("zone-id", 600)
    assert zone.is_on
    zone.schedule_update_ha_state.assert_called()


def test_zone_turn_off_updates_state() -> None:
    """Test stopping a zone optimistically updates its state."""
    zone, controller = _create_zone()
    zone._attr_is_on = True

    zone.turn_off()

    controller.stop_watering.assert_called_once_with()
    assert not zone.is_on
    zone.schedule_update_ha_state.assert_called_once_with()


def test_zone_turn_on_does_not_update_state_when_start_fails() -> None:
    """Test a failed start command does not optimistically update state."""
    zone, controller = _create_zone()
    controller.rachio.zone.start.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        zone.turn_on()

    assert not zone.is_on


def test_zone_turn_off_does_not_update_state_when_stop_fails() -> None:
    """Test a failed stop command does not optimistically update state."""
    zone, controller = _create_zone()
    zone._attr_is_on = True
    controller.stop_watering.side_effect = RuntimeError

    with pytest.raises(RuntimeError):
        zone.turn_off()

    assert zone.is_on
