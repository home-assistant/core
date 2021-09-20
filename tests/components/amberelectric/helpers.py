"""Some common test functions for testing Amber components."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from amberelectric.model.actual_interval import ActualInterval
from amberelectric.model.channel import ChannelType
from amberelectric.model.current_interval import CurrentInterval
from amberelectric.model.forecast_interval import ForecastInterval
from dateutil import parser
import pytest


def generate_actual_interval(channel_type: str, end_time: datetime) -> ActualInterval:
    """Generate a mock actual interval."""
    start_time = end_time - timedelta(minutes=30)
    return ActualInterval(
        duration=30,
        spot_per_kwh=1.0,
        per_kwh=8.0,
        date=start_time.day,
        nem_time=end_time,
        start_time=start_time,
        end_time=end_time,
        renewables=50,
        channel_type=channel_type,
        spike_status=False,
    )


def generate_current_interval(channel_type: str, end_time: datetime) -> CurrentInterval:
    """Generate a mock current price."""
    start_time = end_time - timedelta(minutes=30)
    return CurrentInterval(
        duration=30,
        spot_per_kwh=1.0,
        per_kwh=8.0,
        date=start_time.day,
        nem_time=end_time,
        start_time=start_time,
        end_time=end_time,
        renewables=50,
        channel_type=channel_type,
        spike_status=False,
        estimate=True,
    )


def generate_forecast_interval(
    channel_type: str, end_time: datetime
) -> ForecastInterval:
    """Generate a mock forecast interval."""
    start_time = end_time - timedelta(minutes=30)
    return ForecastInterval(
        duration=30,
        spot_per_kwh=1.0,
        per_kwh=8.0,
        date=start_time.day,
        nem_time=end_time,
        start_time=start_time,
        end_time=end_time,
        renewables=50,
        channel_type=channel_type,
        spike_status=False,
        estimate=True,
    )


GENERAL_ONLY_SITE_ID = "01FG2K6V5TB6X9W0EWPPMZD6MJ"
GENERAL_AND_CONTROLLED_SITE_ID = "01FG2MC8RF7GBC4KJXP3YFZ162"
GENERAL_AND_FEED_IN_SITE_ID = "01FG2MCD8KTRZR9MNNW84VP50S"

GENERAL_CHANNEL = [
    generate_actual_interval("general", parser.parse("2021-09-21T08:00:00+10:00")),
    generate_current_interval("general", parser.parse("2021-09-21T08:30:00+10:00")),
    generate_forecast_interval("general", parser.parse("2021-09-21T09:00:00+10:00")),
]

CONTROLLED_LOAD_CHANNEL = [
    generate_actual_interval(
        "controlledLoad", parser.parse("2021-09-21T08:00:00+10:00")
    ),
    generate_current_interval(
        "controlledLoad", parser.parse("2021-09-21T08:30:00+10:00")
    ),
    generate_forecast_interval(
        "controlledLoad", parser.parse("2021-09-21T09:00:00+10:00")
    ),
]


FEED_IN_CHANNEL = [
    generate_actual_interval("feedIn", parser.parse("2021-09-21T08:00:00+10:00")),
    generate_current_interval("feedIn", parser.parse("2021-09-21T08:30:00+10:00")),
    generate_forecast_interval("feedIn", parser.parse("2021-09-21T09:00:00+10:00")),
]
