"""The test for the Trafikverket Ferry coordinator."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytrafikverket.exceptions import InvalidAuthentication, NoFerryFound
from pytrafikverket.models import FerryStopModel

from homeassistant.components.trafikverket_ferry.const import DOMAIN
from homeassistant.components.trafikverket_ferry.coordinator import next_departuredate
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_UNAVAILABLE, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    get_ferries: list[FerryStopModel],
) -> None:
    """Test the Trafikverket Ferry coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="123",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_ferry.coordinator.TrafikverketFerry.async_get_next_ferry_stops",
        return_value=get_ferries,
    ) as mock_data:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_data.assert_called_once()
        state1 = hass.states.get("sensor.harbor1_departure_from")
        state2 = hass.states.get("sensor.harbor1_departure_to")
        state3 = hass.states.get("sensor.harbor1_departure_time")
        assert state1.state == "Harbor 1"
        assert state2.state == "Harbor 2"
        assert state3.state == str(dt_util.now().year + 1) + "-05-01T12:00:00+00:00"
        mock_data.reset_mock()

        monkeypatch.setattr(
            get_ferries[0],
            "departure_time",
            datetime(dt_util.now().year + 2, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        )

        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state1 = hass.states.get("sensor.harbor1_departure_from")
        state2 = hass.states.get("sensor.harbor1_departure_to")
        state3 = hass.states.get("sensor.harbor1_departure_time")
        assert state1.state == "Harbor 1"
        assert state2.state == "Harbor 2"
        assert state3.state == str(dt_util.now().year + 2) + "-05-01T12:00:00+00:00"
        mock_data.reset_mock()

        mock_data.side_effect = NoFerryFound()
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state1 = hass.states.get("sensor.harbor1_departure_from")
        assert state1.state == STATE_UNAVAILABLE
        mock_data.reset_mock()

        mock_data.return_value = get_ferries
        mock_data.side_effect = None
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        # mock_data.assert_called_once()
        state1 = hass.states.get("sensor.harbor1_departure_from")
        assert state1.state == "Harbor 1"
        mock_data.reset_mock()

        mock_data.side_effect = InvalidAuthentication()
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        mock_data.assert_called_once()
        state1 = hass.states.get("sensor.harbor1_departure_from")
        assert state1.state == STATE_UNAVAILABLE
        mock_data.reset_mock()


async def test_coordinator_next_departuredate(freezer: FrozenDateTimeFactory) -> None:
    """Test the Trafikverket Ferry next_departuredate calculation."""
    freezer.move_to("2022-05-15")
    today = date.today()
    day_list = ["wed", "thu", "fri", "sat"]
    test = next_departuredate(day_list)
    assert test == today + timedelta(days=3)
    day_list = WEEKDAYS
    test = next_departuredate(day_list)
    assert test == today + timedelta(days=0)
    day_list = ["sun"]
    test = next_departuredate(day_list)
    assert test == today + timedelta(days=0)
    freezer.move_to("2022-05-16")
    today = date.today()
    day_list = ["wed", "thu", "fri", "sat", "sun"]
    test = next_departuredate(day_list)
    assert test == today + timedelta(days=2)
