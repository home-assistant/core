"""Fixtures for Trafikverket Ferry integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pytrafikverket.models import FerryStopModel

from homeassistant.components.trafikverket_ferry.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="load_int")
async def load_integration_from_entry(
    hass: HomeAssistant, get_ferries: list[FerryStopModel]
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
def fixture_get_ferries() -> list[FerryStopModel]:
    """Construct FerryStop Mock."""

    depart1 = FerryStopModel(
        ferry_stop_id="13",
        ferry_stop_name="Harbor1lane",
        short_name="Harle",
        deleted=False,
        departure_time=datetime(
            dt_util.now().year + 1, 5, 1, 12, 0, tzinfo=dt_util.UTC
        ),
        other_information=[""],
        deviation_id="0",
        modified_time=datetime(dt_util.now().year, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        from_harbor_name="Harbor 1",
        to_harbor_name="Harbor 2",
        type_name="Turnaround",
    )
    depart2 = FerryStopModel(
        ferry_stop_id="14",
        ferry_stop_name="Harbor1lane",
        short_name="Harle",
        deleted=False,
        departure_time=datetime(dt_util.now().year + 1, 5, 1, 12, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=15),
        other_information=[""],
        deviation_id="0",
        modified_time=datetime(dt_util.now().year, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        from_harbor_name="Harbor 1",
        to_harbor_name="Harbor 2",
        type_name="Turnaround",
    )
    depart3 = FerryStopModel(
        ferry_stop_id="15",
        ferry_stop_name="Harbor1lane",
        short_name="Harle",
        deleted=False,
        departure_time=datetime(dt_util.now().year + 1, 5, 1, 12, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=30),
        other_information=[""],
        deviation_id="0",
        modified_time=datetime(dt_util.now().year, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        from_harbor_name="Harbor 1",
        to_harbor_name="Harbor 2",
        type_name="Turnaround",
    )

    return [depart1, depart2, depart3]
