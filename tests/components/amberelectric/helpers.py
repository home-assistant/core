"""Some common test functions for testing Amber components."""

from datetime import datetime, timedelta

from amberelectric.model.actual_interval import ActualInterval
from amberelectric.model.channel import ChannelType
from amberelectric.model.current_interval import CurrentInterval
from amberelectric.model.forecast_interval import ForecastInterval
from amberelectric.model.interval import Descriptor, SpikeStatus
from dateutil import parser


def generate_actual_interval(
    channel_type: ChannelType, end_time: datetime
) -> ActualInterval:
    """Generate a mock actual interval."""
    start_time = end_time - timedelta(minutes=30)
    return ActualInterval(
        duration=30,
        spot_per_kwh=1.0,
        per_kwh=8.0,
        date=start_time.date(),
        nem_time=end_time,
        start_time=start_time,
        end_time=end_time,
        renewables=50,
        channel_type=channel_type.value,
        spike_status=SpikeStatus.NO_SPIKE.value,
        descriptor=Descriptor.LOW.value,
    )


def generate_current_interval(
    channel_type: ChannelType, end_time: datetime
) -> CurrentInterval:
    """Generate a mock current price."""
    start_time = end_time - timedelta(minutes=30)
    return CurrentInterval(
        duration=30,
        spot_per_kwh=1.0,
        per_kwh=8.0,
        date=start_time.date(),
        nem_time=end_time,
        start_time=start_time,
        end_time=end_time,
        renewables=50.6,
        channel_type=channel_type.value,
        spike_status=SpikeStatus.NO_SPIKE.value,
        descriptor=Descriptor.EXTREMELY_LOW.value,
        estimate=True,
    )


def generate_forecast_interval(
    channel_type: ChannelType, end_time: datetime
) -> ForecastInterval:
    """Generate a mock forecast interval."""
    start_time = end_time - timedelta(minutes=30)
    return ForecastInterval(
        duration=30,
        spot_per_kwh=1.1,
        per_kwh=8.8,
        date=start_time.date(),
        nem_time=end_time,
        start_time=start_time,
        end_time=end_time,
        renewables=50,
        channel_type=channel_type.value,
        spike_status=SpikeStatus.NO_SPIKE.value,
        descriptor=Descriptor.VERY_LOW.value,
        estimate=True,
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
        ChannelType.CONTROLLED_LOAD, parser.parse("2021-09-21T08:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.CONTROLLED_LOAD, parser.parse("2021-09-21T09:00:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.CONTROLLED_LOAD, parser.parse("2021-09-21T09:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.CONTROLLED_LOAD, parser.parse("2021-09-21T10:00:00+10:00")
    ),
]


FEED_IN_CHANNEL = [
    generate_current_interval(
        ChannelType.FEED_IN, parser.parse("2021-09-21T08:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.FEED_IN, parser.parse("2021-09-21T09:00:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.FEED_IN, parser.parse("2021-09-21T09:30:00+10:00")
    ),
    generate_forecast_interval(
        ChannelType.FEED_IN, parser.parse("2021-09-21T10:00:00+10:00")
    ),
]
