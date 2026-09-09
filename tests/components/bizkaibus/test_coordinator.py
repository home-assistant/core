"""Tests for the Bizkaibus coordinator."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.components.bizkaibus.const import CONF_STOP_ID, DOMAIN
from homeassistant.components.bizkaibus.coordinator import BizkaibusUpdateCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_updates_arrivals(hass: HomeAssistant) -> None:
    """Test converting API arrivals to coordinator data."""
    nearest_arrival = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    next_arrival = datetime(2026, 9, 3, 12, 15, tzinfo=UTC)
    timetable = SimpleNamespace(
        name="Central Station",
        arrivals={
            "A": SimpleNamespace(
                line=SimpleNamespace(id="A", route="Route A"),
                nearestArrival=SimpleNamespace(GetUTC=nearest_arrival.isoformat),
                nextArrival=SimpleNamespace(GetUTC=next_arrival.isoformat),
            )
        },
    )
    api = SimpleNamespace(GetTimetable=AsyncMock(return_value=timetable))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.friendly_name == "Central Station"
    assert coordinator.data[0].bus_id == "A"
    assert coordinator.data[0].bus_name == "Route A"
    assert coordinator.data[0].nearest_arrival == nearest_arrival
    assert coordinator.data[0].next_arrival == next_arrival


async def test_coordinator_returns_empty_data_without_timetable(
    hass: HomeAssistant,
) -> None:
    """Test a missing timetable produces no arrivals."""
    api = SimpleNamespace(GetTimetable=AsyncMock(return_value=None))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data == []


async def test_coordinator_uses_current_time_for_missing_nearest_arrival(
    hass: HomeAssistant,
) -> None:
    """Test an arrival without a nearest time remains usable."""
    timetable = SimpleNamespace(
        name=None,
        arrivals={
            "A": SimpleNamespace(
                line=SimpleNamespace(id="A", route="Route A"),
                nearestArrival=None,
                nextArrival=None,
            )
        },
    )
    api = SimpleNamespace(GetTimetable=AsyncMock(return_value=timetable))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data[0].bus_id == "A"
    assert coordinator.data[0].nearest_arrival is not None
    assert coordinator.data[0].next_arrival is None
