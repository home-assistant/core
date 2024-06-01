"""Fixtures for Trafikverket Train integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pytrafikverket.trafikverket_train import TrainStop

from homeassistant.components.trafikverket_train.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG, ENTRY_CONFIG2, OPTIONS_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(name="load_int")
async def load_integration_from_entry(
    hass: HomeAssistant,
    get_trains: list[TrainStop],
    get_train_stop: TrainStop,
) -> MockConfigEntry:
    """Set up the Trafikverket Train integration in Home Assistant."""

    async def setup_config_entry_with_mocked_data(config_entry_id: str) -> None:
        """Set up a config entry with mocked trafikverket data."""
        with (
            patch(
                "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_next_train_stops",
                return_value=get_trains,
            ),
            patch(
                "homeassistant.components.trafikverket_train.coordinator.TrafikverketTrain.async_get_train_stop",
                return_value=get_train_stop,
            ),
            patch(
                "homeassistant.components.trafikverket_train.TrafikverketTrain.async_get_train_station",
            ),
        ):
            await hass.config_entries.async_setup(config_entry_id)
            await hass.async_block_till_done()

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        options=OPTIONS_CONFIG,
        entry_id="1",
        unique_id="stockholmc-uppsalac--['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']",
    )
    config_entry.add_to_hass(hass)
    await setup_config_entry_with_mocked_data(config_entry.entry_id)

    config_entry2 = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG2,
        entry_id="2",
        unique_id="stockholmc-uppsalac-1100-['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']",
    )
    config_entry2.add_to_hass(hass)
    await setup_config_entry_with_mocked_data(config_entry2.entry_id)

    return config_entry


@pytest.fixture(name="get_trains")
def fixture_get_trains() -> list[TrainStop]:
    """Construct TrainStop Mock."""

    depart1 = TrainStop(
        id=13,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        estimated_time_at_location=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        time_at_location=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        other_information=["Some other info"],
        deviations=None,
        modified_time=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )
    depart2 = TrainStop(
        id=14,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=15),
        estimated_time_at_location=None,
        time_at_location=None,
        other_information=["Some other info"],
        deviations=None,
        modified_time=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )
    depart3 = TrainStop(
        id=15,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=30),
        estimated_time_at_location=None,
        time_at_location=None,
        other_information=["Some other info"],
        deviations=None,
        modified_time=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )

    return [depart1, depart2, depart3]


@pytest.fixture(name="get_trains_next")
def fixture_get_trains_next() -> list[TrainStop]:
    """Construct TrainStop Mock."""

    depart1 = TrainStop(
        id=13,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 17, 0, tzinfo=dt_util.UTC),
        estimated_time_at_location=datetime(2023, 5, 1, 17, 0, tzinfo=dt_util.UTC),
        time_at_location=datetime(2023, 5, 1, 17, 0, tzinfo=dt_util.UTC),
        other_information=None,
        deviations=None,
        modified_time=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )
    depart2 = TrainStop(
        id=14,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 17, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=15),
        estimated_time_at_location=None,
        time_at_location=None,
        other_information=["Some other info"],
        deviations=None,
        modified_time=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )
    depart3 = TrainStop(
        id=15,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 17, 0, tzinfo=dt_util.UTC)
        + timedelta(minutes=30),
        estimated_time_at_location=None,
        time_at_location=None,
        other_information=["Some other info"],
        deviations=None,
        modified_time=datetime(2023, 5, 1, 12, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )

    return [depart1, depart2, depart3]


@pytest.fixture(name="get_train_stop")
def fixture_get_train_stop() -> TrainStop:
    """Construct TrainStop Mock."""

    return TrainStop(
        id=13,
        canceled=False,
        advertised_time_at_location=datetime(2023, 5, 1, 11, 0, tzinfo=dt_util.UTC),
        estimated_time_at_location=None,
        time_at_location=datetime(2023, 5, 1, 11, 0, tzinfo=dt_util.UTC),
        other_information=None,
        deviations=None,
        modified_time=datetime(2023, 5, 1, 11, 0, tzinfo=dt_util.UTC),
        product_description=["Regionaltåg"],
    )
