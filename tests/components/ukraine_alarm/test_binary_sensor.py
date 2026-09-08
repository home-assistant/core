"""Test the Ukraine Alarm binary sensors."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.ukraine_alarm.const import DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

REGION_ID = "2.1"

ALL_KEYS = (
    "UNKNOWN",
    "AIR",
    "AIR_RED",
    "AIR_YELLOW",
    "ARTILLERY",
    "URBAN_FIGHTS",
    "CHEMICAL",
    "NUCLEAR",
)


async def setup_integration(
    hass: HomeAssistant, active_alerts: list[dict[str, Any]]
) -> None:
    """Set up the integration against a stubbed region payload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"region": REGION_ID, "name": f"District {REGION_ID}"},
        unique_id=REGION_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ukraine_alarm.coordinator.Client.get_alerts",
        return_value=[{"activeAlerts": active_alerts}],
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_registry: er.EntityRegistry, key: str) -> State:
    """Return the state of the binary sensor for an alert type.

    Entity ids are derived from translated names, which are generated from
    strings.json at build time and so are not available in a plain checkout.
    """
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{REGION_ID}-{key}".lower()
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def _level(alert_level: str) -> dict[str, Any]:
    """Build one reported alert level as the API serves it."""
    return {
        "alertLevel": alert_level,
        "reason": "Ракетна загроза (червоний рівень)",
        "createdAt": "2026-09-08T11:40:15.440927Z",
    }


def _alert(
    alert_type: str = "AIR", levels: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Build an active alert, optionally carrying alert levels."""
    alert: dict[str, Any] = {"type": alert_type}
    if levels is not None:
        alert["activeAlertLevels"] = levels
    return alert


@pytest.mark.parametrize(
    ("active_alerts", "expected_on"),
    [
        ([], set()),
        # An air alert without levels keeps working as it did before.
        ([_alert()], {"AIR"}),
        ([_alert(levels=[])], {"AIR"}),
        ([_alert(levels=[_level("Red")])], {"AIR", "AIR_RED"}),
        ([_alert(levels=[_level("Yellow")])], {"AIR", "AIR_YELLOW"}),
        # One air alert can report both levels at the same time.
        (
            [_alert(levels=[_level("Red"), _level("Yellow")])],
            {"AIR", "AIR_RED", "AIR_YELLOW"},
        ),
        # So can two air alerts that are active for the region at once.
        (
            [_alert(levels=[_level("Yellow")]), _alert(levels=[_level("Red")])],
            {"AIR", "AIR_RED", "AIR_YELLOW"},
        ),
        # The API attaches levels to all alert types, but they are only
        # meaningful for AIR, so the other types are left alone.
        ([_alert("ARTILLERY", [_level("Red")])], {"ARTILLERY"}),
        ([_alert("URBAN_FIGHTS", [_level("Red")])], {"URBAN_FIGHTS"}),
        # A level the integration does not know must not break the update.
        ([_alert(levels=[_level("Purple")])], {"AIR"}),
        (
            [_alert("AIR", [_level("Red")]), _alert("NUCLEAR")],
            {"AIR", "AIR_RED", "NUCLEAR"},
        ),
    ],
)
async def test_alerts(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    active_alerts: list[dict[str, Any]],
    expected_on: set[str],
) -> None:
    """Test each alert turns on exactly the binary sensors it maps to."""
    await setup_integration(hass, active_alerts)

    for key in ALL_KEYS:
        state = _state(hass, entity_registry, key)
        assert state.state == ("on" if key in expected_on else "off"), key
