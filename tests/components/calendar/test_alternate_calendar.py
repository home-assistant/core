"""Tests for alternate calendar support in the calendar component."""

from collections.abc import Callable, Iterable
import dataclasses
import datetime as dt
from typing import Any

import pytest

from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.calendar.alternate_calendar import (
    AlternateCalendarProvider,
    AlternateCalendarRegistry,
    AlternateDate,
)
from homeassistant.components.calendar.helper import (
    api_event_dict_factory,
    event_dict_factory,
)

from .conftest import (
    CHINESE_CALENDAR_TYPE,
    HIJRI_CALENDAR_TYPE,
    MockCalendarEntity,
    MockChineseProvider,
    MockHijriProvider,
)

type DictFactory = Callable[[Iterable[tuple[str, Any]]], dict[str, Any]]


class MinimalProvider(MockHijriProvider):
    """Provider with a configurable calendar type for testing display_name."""

    def __init__(self, calendar_type: str) -> None:
        """Initialize the provider."""
        self.calendar_type = calendar_type


class SupportingCalendarEntity(MockCalendarEntity):
    """Calendar entity that reports alternate calendar support."""

    @property
    def supported_alternate_calendars(self) -> list[str]:
        """Return the supported alternate calendar types."""
        return [HIJRI_CALENDAR_TYPE]


def make_alternate_date(
    calendar_type: str = HIJRI_CALENDAR_TYPE,
    display_name: str = "1 Muharram 1447",
    date_str: str = "2025-06-26",
    metadata: dict[str, Any] | None = None,
) -> AlternateDate:
    """Create an AlternateDate for use in tests."""
    return AlternateDate(
        calendar_type=calendar_type,
        display_name=display_name,
        date_str=date_str,
        metadata=metadata,
    )


def make_event(
    alternate_dates: list[AlternateDate] | None = None,
    start: dt.date | dt.datetime = dt.date(2025, 6, 26),
    end: dt.date | dt.datetime = dt.date(2025, 6, 27),
) -> CalendarEvent:
    """Create a CalendarEvent for use in tests."""
    return CalendarEvent(
        start=start,
        end=end,
        summary="Test Event",
        alternate_dates=alternate_dates,
    )


def test_alternate_date() -> None:
    """Test an alternate date carries its calendar information."""
    alternate_date = make_alternate_date(metadata={"era": "AH"})
    assert alternate_date.calendar_type == HIJRI_CALENDAR_TYPE
    assert alternate_date.display_name == "1 Muharram 1447"
    assert alternate_date.date_str == "2025-06-26"
    assert alternate_date.metadata == {"era": "AH"}
    assert make_alternate_date().metadata is None


def test_provider_cannot_be_instantiated() -> None:
    """Test the abstract base class cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AlternateCalendarProvider()  # type: ignore[abstract]


@pytest.mark.parametrize(
    ("calendar_type", "expected"),
    [
        ("hijri", "Hijri"),
        ("chinese_lunar", "Chinese Lunar"),
        ("hebrew", "Hebrew"),
    ],
)
def test_provider_default_display_name(calendar_type: str, expected: str) -> None:
    """Test the default display name derives a title-cased name."""
    assert MinimalProvider(calendar_type).display_name == expected


def test_provider_converts_date() -> None:
    """Test a provider converts a Gregorian date."""
    alternate_date = MockHijriProvider().convert_date(dt.date(2025, 6, 26))
    assert alternate_date == AlternateDate(
        calendar_type=HIJRI_CALENDAR_TYPE,
        display_name="Hijri date for 2025-06-26",
        date_str="2025-06-26",
        metadata={"era": "AH"},
    )


def test_registry_register_and_list(
    registry: type[AlternateCalendarRegistry],
) -> None:
    """Test registering providers makes them retrievable and listed."""
    registry.register(HIJRI_CALENDAR_TYPE)(MockHijriProvider)
    registry.register(CHINESE_CALENDAR_TYPE)(MockChineseProvider)

    assert registry.get_provider(HIJRI_CALENDAR_TYPE) is MockHijriProvider
    assert registry.get_provider(CHINESE_CALENDAR_TYPE) is MockChineseProvider
    assert sorted(registry.list_providers()) == [
        CHINESE_CALENDAR_TYPE,
        HIJRI_CALENDAR_TYPE,
    ]


def test_registry_get_unregistered_provider(
    registry: type[AlternateCalendarRegistry],
) -> None:
    """Test getting an unregistered provider raises KeyError."""
    with pytest.raises(KeyError, match="nonexistent"):
        registry.get_provider("nonexistent")


def test_registry_duplicate_registration_overwrites(
    registry: type[AlternateCalendarRegistry],
) -> None:
    """Test registering the same type twice overwrites the provider."""
    registry.register(HIJRI_CALENDAR_TYPE)(MockHijriProvider)
    registry.register(HIJRI_CALENDAR_TYPE)(MockChineseProvider)

    assert registry.get_provider(HIJRI_CALENDAR_TYPE) is MockChineseProvider
    assert registry.list_providers() == [HIJRI_CALENDAR_TYPE]


def test_calendar_event_alternate_dates() -> None:
    """Test an event carries alternate dates."""
    alternate_dates = [make_alternate_date()]
    assert make_event(alternate_dates).alternate_dates == alternate_dates
    assert make_event().alternate_dates is None


def test_event_as_dict_serializes_alternate_dates() -> None:
    """Test the event dict serializes alternate dates and defaults metadata."""
    event = make_event(
        [
            make_alternate_date(metadata={"era": "AH"}),
            make_alternate_date(
                calendar_type=CHINESE_CALENDAR_TYPE,
                display_name="Chinese date",
                date_str="2025-01-29",
            ),
        ]
    )

    assert event.as_dict()["alternate_dates"] == [
        {
            "calendar_type": HIJRI_CALENDAR_TYPE,
            "display_name": "1 Muharram 1447",
            "date_str": "2025-06-26",
            "metadata": {"era": "AH"},
        },
        {
            "calendar_type": CHINESE_CALENDAR_TYPE,
            "display_name": "Chinese date",
            "date_str": "2025-01-29",
            "metadata": {},
        },
    ]


def test_event_as_dict_omits_alternate_dates() -> None:
    """Test the event dict omits alternate dates when there are none."""
    assert "alternate_dates" not in make_event().as_dict()


@pytest.mark.parametrize("factory", [api_event_dict_factory, event_dict_factory])
def test_event_dict_factories_serialize_alternate_dates(factory: DictFactory) -> None:
    """Test both event dict factories serialize alternate dates the same way."""
    result = dataclasses.asdict(
        make_event(
            [make_alternate_date(), make_alternate_date(metadata={"era": "AH"})]
        ),
        dict_factory=factory,
    )

    assert result["alternate_dates"] == [
        {
            "calendar_type": HIJRI_CALENDAR_TYPE,
            "display_name": "1 Muharram 1447",
            "date_str": "2025-06-26",
            "metadata": {},
        },
        {
            "calendar_type": HIJRI_CALENDAR_TYPE,
            "display_name": "1 Muharram 1447",
            "date_str": "2025-06-26",
            "metadata": {"era": "AH"},
        },
    ]


@pytest.mark.parametrize("factory", [api_event_dict_factory, event_dict_factory])
def test_event_dict_factories_omit_alternate_dates(factory: DictFactory) -> None:
    """Test both event dict factories omit alternate dates when there are none."""
    result = dataclasses.asdict(make_event(), dict_factory=factory)
    assert "alternate_dates" not in result


@pytest.mark.usefixtures("set_time_zone")
@pytest.mark.parametrize(
    ("start", "end", "expected_start", "expected_end"),
    [
        (
            dt.date(2025, 6, 26),
            dt.date(2025, 6, 27),
            {"date": "2025-06-26"},
            {"date": "2025-06-27"},
        ),
        (
            dt.datetime(2025, 6, 26, 10, 0, tzinfo=dt.UTC),
            dt.datetime(2025, 6, 26, 12, 0, tzinfo=dt.UTC),
            {"dateTime": "2025-06-26T04:00:00-06:00"},
            {"dateTime": "2025-06-26T06:00:00-06:00"},
        ),
    ],
)
async def test_api_event_dict_factory_start_end(
    start: dt.date | dt.datetime,
    end: dt.date | dt.datetime,
    expected_start: dict[str, str],
    expected_end: dict[str, str],
) -> None:
    """Test the API event dict uses the date and dateTime shapes."""
    result = dataclasses.asdict(
        make_event(start=start, end=end), dict_factory=api_event_dict_factory
    )
    assert result["start"] == expected_start
    assert result["end"] == expected_end


def test_supported_alternate_calendars_default() -> None:
    """Test alternate calendar support defaults to an empty list."""
    assert MockCalendarEntity("test").supported_alternate_calendars == []


def test_capability_attributes_without_supported_alternate_calendars() -> None:
    """Test capability attributes are unchanged without alternate calendars."""
    assert MockCalendarEntity("test").capability_attributes is None


def test_capability_attributes_with_supported_alternate_calendars() -> None:
    """Test alternate calendar support is exposed as a capability attribute."""
    assert SupportingCalendarEntity("test").capability_attributes == {
        "supported_alternate_calendars": [HIJRI_CALENDAR_TYPE]
    }
