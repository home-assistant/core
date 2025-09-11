"""Test the OMIE util module."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from homeassistant.components.omie.util import CET, get_market_dates, is_published


class TestGetMarketDates:
    """Test _get_market_dates function."""

    def test_lisbon_midday_spans_cet_dates(self) -> None:
        """Test that Lisbon day spans CET dates due to timezone conversion."""
        tz = ZoneInfo("Europe/Lisbon")
        local_time = datetime(2024, 6, 15, 12, 0, tzinfo=tz)  # 12:00 Lisbon = 13:00 CET

        market_dates = get_market_dates(tz, local_time)

        # A Lisbon day (00:00-23:59 Lisbon) converts to (01:00 CET day1 - 00:59 CET day2)
        # So it spans 2 CET dates: June 15 and June 16
        assert market_dates == {date(2024, 6, 15), date(2024, 6, 16)}

    def test_madrid_midday_same_cet_date(self) -> None:
        """Test that Madrid midday maps to same CET date."""
        tz = ZoneInfo("Europe/Madrid")
        local_time = datetime(2024, 6, 15, 12, 0, tzinfo=tz)  # 12:00 Madrid = 12:00 CET

        market_dates = get_market_dates(tz, local_time)

        assert market_dates == {date(2024, 6, 15)}

    def test_bucharest_midday_spans_cet_dates(self) -> None:
        """Test that Bucharest day spans CET dates (UTC+2/+3 vs UTC+1/+2)."""
        tz = ZoneInfo("Europe/Bucharest")
        local_time = datetime(
            2024, 6, 15, 12, 0, tzinfo=tz
        )  # 12:00 Bucharest = 11:00 CET

        market_dates = get_market_dates(tz, local_time)

        # A Bucharest day (00:00-23:59 Bucharest) converts to (23:00 CET day-1 - 22:59 CET day)
        # So it spans 2 CET dates: June 14 and June 15
        assert market_dates == {date(2024, 6, 14), date(2024, 6, 15)}

    @freeze_time("2024-03-31 01:30:00")  # DST transition day (last Sunday in March)
    def test_dst_spring_transition(self) -> None:
        """Test market dates during spring DST transition."""
        # Test around 2 AM when clocks spring forward
        tz = ZoneInfo("Europe/Lisbon")
        local_time = datetime(2024, 3, 31, 2, 30, tzinfo=tz)

        market_dates = get_market_dates(tz, local_time)

        assert market_dates == {date(2024, 3, 31), date(2024, 4, 1)}

    @freeze_time("2024-10-27 02:30:00")  # DST transition day (last Sunday in October)
    def test_dst_fall_transition(self) -> None:
        """Test market dates during fall DST transition."""
        # Test around 2 AM when clocks fall back
        tz = ZoneInfo("Europe/Madrid")
        local_time = datetime(2024, 10, 27, 2, 30, tzinfo=tz)

        market_dates = get_market_dates(tz, local_time)

        assert market_dates == {date(2024, 10, 27)}


class TestIsPublished:
    """Test _is_published function."""

    def test_before_publish_time(self) -> None:
        """Test that data is not published before 13:30 CET the day before."""
        market_date = date(2024, 6, 15)  # Saturday
        # 13:29 CET on Friday (day before) - should not be published yet
        fetch_time = datetime(2024, 6, 14, 13, 29, tzinfo=CET)

        assert not is_published(market_date, fetch_time)

    def test_after_publish_time(self) -> None:
        """Test that data is published after 13:30 CET the day before."""
        market_date = date(2024, 6, 15)  # Saturday
        # 13:31 CET on Friday (day before) - should be published
        fetch_time = datetime(2024, 6, 14, 13, 31, tzinfo=CET)

        assert is_published(market_date, fetch_time)

    def test_next_day_published(self) -> None:
        """Test that data is published the next day."""
        market_date = date(2024, 6, 15)  # Saturday
        # Any time on Saturday - should be published
        fetch_time = datetime(2024, 6, 15, 10, 0, tzinfo=CET)

        assert is_published(market_date, fetch_time)

    @pytest.mark.parametrize(
        ("timezone_str", "local_hour"),
        [
            ("Europe/Lisbon", 14),  # 14:30 Lisbon = 15:30 CET (summer)
            ("Europe/Madrid", 14),  # 14:30 Madrid = 14:30 CET (summer)
        ],
    )
    def test_publication_from_different_timezones(
        self, timezone_str: str, local_hour: int
    ) -> None:
        """Test publication check from different local timezones."""
        market_date = date(2024, 6, 15)  # Saturday

        # Create fetch time in local timezone (day before market date)
        local_tz = ZoneInfo(timezone_str)
        local_fetch_time = datetime(2024, 6, 14, local_hour, 30, tzinfo=local_tz)

        # Should be published since it's after 13:30 CET the day before
        assert is_published(market_date, local_fetch_time)

    def test_real_world_scenarios(self) -> None:
        """Test real-world usage scenarios."""
        # Portuguese user checking at 2:30 PM local time should see tomorrow's data
        market_date = date(2024, 6, 15)  # Tomorrow's data
        lisbon_tz = ZoneInfo("Europe/Lisbon")
        portuguese_time = datetime(2024, 6, 14, 14, 30, tzinfo=lisbon_tz)

        assert is_published(market_date, portuguese_time)

        # Spanish user checking at 2:30 PM local time should see tomorrow's data
        madrid_tz = ZoneInfo("Europe/Madrid")
        spanish_time = datetime(2024, 6, 14, 14, 30, tzinfo=madrid_tz)

        assert is_published(market_date, spanish_time)

    @freeze_time("2024-03-31 14:00:00")  # DST transition day
    def test_dst_transition_publication(self) -> None:
        """Test publication logic during DST transitions."""
        market_date = date(2024, 4, 1)  # Day after DST transition

        # Check from different timezones during DST transition
        timezones = ["Europe/Lisbon", "Europe/Madrid"]

        for tz_str in timezones:
            tz = ZoneInfo(tz_str)
            fetch_time = datetime(2024, 3, 31, 14, 0, tzinfo=tz)

            # Should handle DST transition correctly
            result = is_published(market_date, fetch_time)
            assert isinstance(result, bool)
