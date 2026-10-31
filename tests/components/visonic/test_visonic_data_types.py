"""Tests for Visonic runtime and coordinator data types."""

from datetime import date, datetime
from enum import Enum

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.visonic.const import CONF_PANEL_NUMBER, DOMAIN
from homeassistant.components.visonic.visonic_data_types import (
    VisonicCoordinatorData,
    get_panels_by_config_state,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


class ExampleMode(Enum):
    """Example enum for recursive conversion tests."""

    active = 1


def test_coordinator_data_recursive_conversions() -> None:
    """Convert nested mappings, sequences, sets, dates, and enum names."""
    data = VisonicCoordinatorData()
    value = {
        "none": None,
        "mode": ExampleMode.active,
        "date": date(2026, 1, 2),
        "datetime": datetime(2026, 1, 2, 3, 4),
        "values": (1, [2], {3}),
    }
    assert data._convert_recursive(True, value) == {
        "none": None,
        "mode": "Active",
        "date": "2026-01-02",
        "datetime": "2026-01-02T03:04:00",
        "values": [1, [2], [3]],
    }
    assert data._convert_recursive(False, ExampleMode.active) is ExampleMode.active
    assert data._convert_recursive(False, "plain") == "plain"


@pytest.mark.parametrize(
    ("state_set", "invert", "expected"),
    [
        pytest.param(None, False, [1, 3, 5], id="all-states"),
        pytest.param(None, True, [1, 3, 5], id="all-states-inverted"),
        pytest.param({ConfigEntryState.LOADED}, False, [1], id="loaded"),
        pytest.param({ConfigEntryState.LOADED}, True, [3, 5], id="not-loaded"),
        pytest.param(
            {ConfigEntryState.NOT_LOADED, ConfigEntryState.SETUP_RETRY},
            False,
            [3, 5],
            id="multiple-states",
        ),
        pytest.param(set(), False, [], id="no-states"),
        pytest.param(set(), True, [1, 3, 5], id="no-states-inverted"),
    ],
)
def test_get_panels_by_config_state(
    hass: HomeAssistant,
    state_set: set[ConfigEntryState] | None,
    invert: bool,
    expected: list[int],
) -> None:
    """Read panel IDs from saved data and filter by config-entry state."""
    for panel_id, state in (
        (1, ConfigEntryState.LOADED),
        (3, ConfigEntryState.NOT_LOADED),
        (5, ConfigEntryState.SETUP_RETRY),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN, data={CONF_PANEL_NUMBER: str(panel_id)}, state=state
        )
        entry.add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)
    MockConfigEntry(domain="other", data={CONF_PANEL_NUMBER: 7}).add_to_hass(hass)
    assert get_panels_by_config_state(hass, state_set, invert) == expected
