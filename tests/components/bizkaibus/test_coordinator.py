"""Tests for the Bizkaibus coordinator."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bizkaibus import BizkaibusConnectionError, BizkaibusParseError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bizkaibus.const import CONF_STOP_ID, DOMAIN, SCAN_INTERVAL
from homeassistant.components.bizkaibus.coordinator import BizkaibusUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_coordinator_updates_arrivals(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test converting API arrivals to coordinator data."""
    nearest_arrival = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    next_arrival = datetime(2026, 9, 3, 12, 15, tzinfo=UTC)
    timetable = SimpleNamespace(
        name="Central Station",
        arrivals={
            "A": SimpleNamespace(
                line=SimpleNamespace(id="A", route="Route A"),
                nearest_arrival=SimpleNamespace(get_utc=nearest_arrival.isoformat),
                next_arrival=SimpleNamespace(get_utc=next_arrival.isoformat),
            )
        },
    )
    api = SimpleNamespace(get_timetable=AsyncMock(return_value=timetable))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    remove_listener = coordinator.async_add_listener(lambda: None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    remove_listener()

    assert coordinator.last_update_success
    assert coordinator.friendly_name == "Central Station"
    assert coordinator.data[0].bus_id == "A"
    assert coordinator.data[0].bus_name == "Route A"
    assert coordinator.data[0].nearest_arrival == nearest_arrival
    assert coordinator.data[0].next_arrival == next_arrival


async def test_coordinator_returns_empty_data_without_timetable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a missing timetable produces no arrivals."""
    api = SimpleNamespace(get_timetable=AsyncMock(return_value=None))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    remove_listener = coordinator.async_add_listener(lambda: None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    remove_listener()

    assert coordinator.last_update_success
    assert coordinator.data == []


@pytest.mark.parametrize(
    "error",
    [BizkaibusConnectionError(), BizkaibusParseError()],
    ids=["connection", "parse"],
)
async def test_coordinator_raises_update_failed_on_api_error(
    hass: HomeAssistant, error: BizkaibusConnectionError | BizkaibusParseError
) -> None:
    """Test API errors are reported as update failures."""
    api = SimpleNamespace(get_timetable=AsyncMock(side_effect=error))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    with pytest.raises(UpdateFailed) as err:
        await coordinator._async_update_data()

    assert err.value.__cause__ is error


async def test_coordinator_skips_arrivals_without_nearest_arrival(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test arrivals without a nearest time are skipped."""
    nearest_arrival = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
    timetable = SimpleNamespace(
        name=None,
        arrivals={
            "A": SimpleNamespace(
                line=SimpleNamespace(id="A", route="Route A"),
                nearest_arrival=None,
                next_arrival=None,
            ),
            "B": SimpleNamespace(
                line=SimpleNamespace(id="B", route="Route B"),
                nearest_arrival=SimpleNamespace(get_utc=nearest_arrival.isoformat),
                next_arrival=None,
            ),
        },
    )
    api = SimpleNamespace(get_timetable=AsyncMock(return_value=timetable))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_STOP_ID: "1234"})
    entry.add_to_hass(hass)
    coordinator = BizkaibusUpdateCoordinator(hass, api, entry)

    remove_listener = coordinator.async_add_listener(lambda: None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    remove_listener()

    assert coordinator.last_update_success
    assert len(coordinator.data) == 1
    assert coordinator.data[0].bus_id == "B"
    assert coordinator.data[0].nearest_arrival == nearest_arrival
