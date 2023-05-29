"""The test for the Trafikverket sensor platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from pytrafikverket.trafikverket_ferry import FerryStop

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_sensor(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_ferries: list[FerryStop],
) -> None:
    """Test the Trafikverket Ferry sensor."""
    state1 = hass.states.get("sensor.harbor1_departure_from")
    state2 = hass.states.get("sensor.harbor1_departure_to")
    state3 = hass.states.get("sensor.harbor1_departure_time")
    assert state1.state == "Harbor 1"
    assert state2.state == "Harbor 2"
    assert state3.state == str(dt_util.now().year + 1) + "-05-01T12:00:00+00:00"
    assert state1.attributes["icon"] == "mdi:ferry"
    assert state1.attributes["other_information"] == [""]
    assert state2.attributes["icon"] == "mdi:ferry"

    monkeypatch.setattr(get_ferries[0], "other_information", ["Nothing exiting"])

    with patch(
        "homeassistant.components.trafikverket_ferry.coordinator.TrafikverketFerry.async_get_next_ferry_stops",
        return_value=get_ferries,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=6),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("sensor.harbor1_departure_from")
    assert state1.state == "Harbor 1"
    assert state1.attributes["other_information"] == ["Nothing exiting"]
