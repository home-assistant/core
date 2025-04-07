"""Some common test functions for testing Amber components."""

from datetime import datetime, timedelta

from amberelectric.models.actual_interval import ActualInterval
from amberelectric.models.channel import ChannelType
from amberelectric.models.current_interval import CurrentInterval
from amberelectric.models.forecast_interval import ForecastInterval
from amberelectric.models.interval import Interval
from amberelectric.models.price_descriptor import PriceDescriptor
from amberelectric.models.spike_status import SpikeStatus
from dateutil import parser


def generate_actual_interval(channel_type: ChannelType, end_time: datetime) -> Interval:
    """Generate a mock actual interval."""
    start_time = end_time - timedelta(minutes=30)
    return Interval(
        ActualInterval(
            type="ActualInterval",
            duration=30,
            spot_per_kwh=1.0,
            per_kwh=8.0,
            date=start_time.date(),
            nem_time=end_time,
            start_time=start_time,
            end_time=end_time,
            renewables=50,
            channel_type=channel_type,
            spike_status=SpikeStatus.NONE,
            descriptor=PriceDescriptor.LOW,
        )
    )


def generate_current_interval(
    channel_type: ChannelType, end_time: datetime
) -> Interval:
    """Generate a mock current price."""
    start_time = end_time - timedelta(minutes=30)
    return Interval(
        CurrentInterval(
            type="CurrentInterval",
            duration=30,
            spot_per_kwh=1.0,
            per_kwh=8.0,
            date=start_time.date(),
            nem_time=end_time,
            start_time=start_time,
            end_time=end_time,
            renewables=50.6,
            channel_type=channel_type,
            spike_status=SpikeStatus.NONE,
            descriptor=PriceDescriptor.EXTREMELYLOW,
            estimate=True,
        )
    )


def generate_forecast_interval(
    channel_type: ChannelType, end_time: datetime
) -> Interval:
    """Generate a mock forecast interval."""
    start_time = end_time - timedelta(minutes=30)
    return Interval(
        ForecastInterval(
            type="ForecastInterval",
            duration=30,
            spot_per_kwh=1.1,
            per_kwh=8.8,
            date=start_time.date(),
            nem_time=end_time,
            start_time=start_time,
            end_time=end_time,
            renewables=50,
            channel_type=channel_type,
            spike_status=SpikeStatus.NONE,
            descriptor=PriceDescriptor.VERYLOW,
            estimate=True,
        )
    )


GENERAL_ONLY_SITE_ID = "01FG2K6V5TB6X9W0EWPPMZD6MJ"
GENERAL_AND_CONTROLLED_SITE_ID = "01FG2MC8RF7GBC4KJXP3YFZ162"
GENERAL_AND_FEED_IN_SITE_ID = "01FG2MCD8KTRZR9MNNW84VP50S"
GENERAL_AND_CONTROLLED_FEED_IN_SITE_ID = "01FG2MCD8KTRZR9MNNW847S50S"

GENERAL_CHANNEL = [
    generate_current_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T08:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T09:00:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T09:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.GENERAL, parser.parse("2021-09-21T10:00:00+10:00")
    ),
]

CONTROLLED_LOAD_CHANNEL = [
    generate_current_interval(
        ChannelType.CONTROLLEDLOAD, parser.parse("2021-09-21T08:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.CONTROLLEDLOAD, parser.parse("2021-09-21T09:00:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.CONTROLLEDLOAD, parser.parse("2021-09-21T09:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.CONTROLLEDLOAD, parser.parse("2021-09-21T10:00:00+10:00")
    ),
]


FEED_IN_CHANNEL = [
    generate_current_interval(
        ChannelType.FEEDIN, parser.parse("2021-09-21T08:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.FEEDIN, parser.parse("2021-09-21T09:00:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.FEEDIN, parser.parse("2021-09-21T09:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.FEEDIN, parser.parse("2021-09-21T10:00:00+10:00")
    ),
]
