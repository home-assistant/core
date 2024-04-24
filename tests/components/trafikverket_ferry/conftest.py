"""Fixtures for Trafikverket Ferry integration tests."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pytrafikverket.trafikverket_ferry import FerryStop

from homeassistant.components.trafikverket_ferry.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="load_int")
async def load_integration_from_entry(
    hass: HomeAssistant, get_ferries: list[FerryStop]
) -> MockConfigEntry:
    """Set up the Trafikverket Ferry integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="123",
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_ferry.coordinator.TrafikverketFerry.async_get_next_ferry_stops",
        return_value=get_ferries,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="get_ferries")
def fixture_get_ferries() -> list[FerryStop]:
    """Construct FerryStop Mock."""

    depart1 = FerryStop(
        "13",
        False,
        datetime(dt_util.now().year + 1, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        [""],
        "0",
        datetime(dt_util.now().year, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        "Harbor 1",
        "Harbor 2",
    )
    depart2 = FerryStop(
        "14",
        False,
        datetime(dt_util.now().year + 1, 5, 1, 12, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=15),
        [""],
        "0",
        datetime(dt_util.now().year, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        "Harbor 1",
        "Harbor 2",
    )
    depart3 = FerryStop(
        "15",
        False,
        datetime(dt_util.now().year + 1, 5, 1, 12, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=30),
        [""],
        "0",
        datetime(dt_util.now().year, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        "Harbor 1",
        "Harbor 2",
    )

    return [depart1, depart2, depart3]
