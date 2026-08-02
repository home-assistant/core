"""The tests for the Sun helpers."""

from datetime import date, datetime, timedelta

from astral import LocationInfo
from astral.location import Location
import astral.sun
from freezegun import freeze_time
import pytest

from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import sun
from homeassistant.util import dt as dt_util


def test_next_events(hass: HomeAssistant) -> None:
    """Test retrieving next sun events."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)

    utc_today = utc_now.date()

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    mod = -1
    while True:
        next_dawn = astral.sun.dawn(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_dawn > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_dusk = astral.sun.dusk(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_dusk > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_midnight = astral.sun.midnight(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_midnight > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_noon = astral.sun.noon(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_noon > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_rising = astral.sun.sunrise(
            location.observer, date=utc_today + timedelta(days=mod)
        )
        if next_rising > utc_now:
            break
        mod += 1

    mod = -1
    while True:
        next_setting = astral.sun.sunset(
            location.observer, utc_today + timedelta(days=mod)
        )
        if next_setting > utc_now:
            break
        mod += 1

    with freeze_time(utc_now):
        assert next_dawn == sun.get_astral_event_next(hass, "dawn")
        assert next_dusk == sun.get_astral_event_next(hass, "dusk")
        assert next_midnight == sun.get_astral_event_next(hass, "midnight")
        assert next_noon == sun.get_astral_event_next(hass, "noon")
        assert next_rising == sun.get_astral_event_next(hass, SUN_EVENT_SUNRISE)
        assert next_setting == sun.get_astral_event_next(hass, SUN_EVENT_SUNSET)


def test_date_events(hass: HomeAssistant) -> None:
    """Test retrieving next sun events."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)

    utc_today = utc_now.date()

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    local_tz = dt_util.get_default_time_zone()
    dawn = astral.sun.dawn(location.observer, utc_today, tzinfo=local_tz)
    dusk = astral.sun.dusk(location.observer, utc_today, tzinfo=local_tz)
    midnight = astral.sun.midnight(location.observer, utc_today, tzinfo=local_tz)
    noon = astral.sun.noon(location.observer, utc_today, tzinfo=local_tz)
    sunrise = astral.sun.sunrise(location.observer, utc_today, tzinfo=local_tz)
    sunset = astral.sun.sunset(location.observer, utc_today, tzinfo=local_tz)

    assert dawn == sun.get_astral_event_date(hass, "dawn", utc_today)
    assert dusk == sun.get_astral_event_date(hass, "dusk", utc_today)
    assert midnight == sun.get_astral_event_date(hass, "midnight", utc_today)
    assert noon == sun.get_astral_event_date(hass, "noon", utc_today)
    assert sunrise == sun.get_astral_event_date(hass, SUN_EVENT_SUNRISE, utc_today)
    assert sunset == sun.get_astral_event_date(hass, SUN_EVENT_SUNSET, utc_today)


def test_date_events_default_date(hass: HomeAssistant) -> None:
    """Test retrieving next sun events."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)

    utc_today = utc_now.date()

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    local_tz = dt_util.get_default_time_zone()
    dawn = astral.sun.dawn(location.observer, date=utc_today, tzinfo=local_tz)
    dusk = astral.sun.dusk(location.observer, date=utc_today, tzinfo=local_tz)
    midnight = astral.sun.midnight(location.observer, date=utc_today, tzinfo=local_tz)
    noon = astral.sun.noon(location.observer, date=utc_today, tzinfo=local_tz)
    sunrise = astral.sun.sunrise(location.observer, date=utc_today, tzinfo=local_tz)
    sunset = astral.sun.sunset(location.observer, date=utc_today, tzinfo=local_tz)

    with freeze_time(utc_now):
        assert dawn == sun.get_astral_event_date(hass, "dawn", utc_today)
        assert dusk == sun.get_astral_event_date(hass, "dusk", utc_today)
        assert midnight == sun.get_astral_event_date(hass, "midnight", utc_today)
        assert noon == sun.get_astral_event_date(hass, "noon", utc_today)
        assert sunrise == sun.get_astral_event_date(hass, SUN_EVENT_SUNRISE, utc_today)
        assert sunset == sun.get_astral_event_date(hass, SUN_EVENT_SUNSET, utc_today)


def test_date_events_accepts_datetime(hass: HomeAssistant) -> None:
    """Test retrieving next sun events."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)

    utc_today = utc_now.date()

    location = LocationInfo(
        latitude=hass.config.latitude, longitude=hass.config.longitude
    )

    local_tz = dt_util.get_default_time_zone()
    dawn = astral.sun.dawn(location.observer, date=utc_today, tzinfo=local_tz)
    dusk = astral.sun.dusk(location.observer, date=utc_today, tzinfo=local_tz)
    midnight = astral.sun.midnight(location.observer, date=utc_today, tzinfo=local_tz)
    noon = astral.sun.noon(location.observer, date=utc_today, tzinfo=local_tz)
    sunrise = astral.sun.sunrise(location.observer, date=utc_today, tzinfo=local_tz)
    sunset = astral.sun.sunset(location.observer, date=utc_today, tzinfo=local_tz)

    assert dawn == sun.get_astral_event_date(hass, "dawn", utc_now)
    assert dusk == sun.get_astral_event_date(hass, "dusk", utc_now)
    assert midnight == sun.get_astral_event_date(hass, "midnight", utc_now)
    assert noon == sun.get_astral_event_date(hass, "noon", utc_now)
    assert sunrise == sun.get_astral_event_date(hass, SUN_EVENT_SUNRISE, utc_now)
    assert sunset == sun.get_astral_event_date(hass, SUN_EVENT_SUNSET, utc_now)


def test_date_events_match_local_day_west_of_utc(hass: HomeAssistant) -> None:
    """Sunset for a negative-longitude location must land on the requested local day.

    San Diego's evening sunset already falls on the next UTC day, so a lookup
    without a timezone hint can return the previous local day's sunset.
    """
    requested_date = date(2025, 5, 20)

    sunset = sun.get_astral_event_date(hass, SUN_EVENT_SUNSET, requested_date)

    assert sunset is not None
    assert dt_util.as_local(sunset).date() == requested_date


def test_is_up(hass: HomeAssistant) -> None:
    """Test retrieving next sun events."""
    utc_now = datetime(2016, 11, 1, 12, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(utc_now):
        assert not sun.is_up(hass)

    utc_now = datetime(2016, 11, 1, 18, 0, 0, tzinfo=dt_util.UTC)
    with freeze_time(utc_now):
        assert sun.is_up(hass)


def test_norway_in_june(hass: HomeAssistant) -> None:
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8

    june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

    assert sun.get_astral_event_next(hass, SUN_EVENT_SUNRISE, june) == datetime(
        2016, 7, 25, 23, 26, 30, 480352, tzinfo=dt_util.UTC
    )
    assert sun.get_astral_event_next(hass, SUN_EVENT_SUNSET, june) == datetime(
        2016, 7, 25, 22, 16, 21, 829089, tzinfo=dt_util.UTC
    )
    assert sun.get_astral_event_date(hass, SUN_EVENT_SUNRISE, june) is None
    assert sun.get_astral_event_date(hass, SUN_EVENT_SUNSET, june) is None


def test_impossible_elevation(hass: HomeAssistant) -> None:
    """Test altitude where the sun can't set."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8
    hass.config.elevation = 10000000

    june = datetime(2016, 6, 1, tzinfo=dt_util.UTC)

    with pytest.raises(ValueError):
        sun.get_astral_event_next(hass, SUN_EVENT_SUNRISE, june)


def test_deprecated_get_astral_location(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the deprecated get_astral_location helper."""
    location, elevation = sun.get_astral_location(hass)

    observer = sun.get_astral_observer(hass)
    assert location.latitude == observer.latitude
    assert location.longitude == observer.longitude
    assert elevation == observer.elevation
    assert (
        "The deprecated function get_astral_location was called. It will be removed "
        "in HA Core 2027.7. Use homeassistant.helpers.sun.get_astral_observer instead"
    ) in caplog.text


def test_deprecated_get_location_astral_event_next(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the deprecated get_location_astral_event_next helper."""
    utc_now = datetime(2016, 11, 1, 8, 0, 0, tzinfo=dt_util.UTC)
    location = Location(
        LocationInfo(
            "",
            "",
            str(hass.config.time_zone),
            hass.config.latitude,
            hass.config.longitude,
        )
    )

    assert sun.get_location_astral_event_next(
        location, hass.config.elevation, SUN_EVENT_SUNRISE, utc_now
    ) == sun.get_astral_event_next(hass, SUN_EVENT_SUNRISE, utc_now)
    assert (
        "The deprecated function get_location_astral_event_next was called. It will "
        "be removed in HA Core 2027.7. Use "
        "homeassistant.helpers.sun.get_observer_astral_event_next instead"
    ) in caplog.text
