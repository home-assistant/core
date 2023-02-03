"""Test timezone functions."""
from datetime import datetime

import pytz

from homeassistant.util.timezone import (
    get_locality_time_and_utc,
    get_multiple_zones_time,
    get_utc,
)


# Europe/London = GMT+0
def test_get_locality_utc():
    """Test get valid utc from other country."""
    assert 0 == get_utc("Europe/London")


def test_get_locality_utc_different_than_0():
    """Test get valid utc from utc+3 and utc-3."""
    assert -3 == get_utc("America/Sao_Paulo")
    assert 3 == get_utc("Europe/Moscow")


def test_get_current_hour():
    """Test getting currently hour."""
    assert int(datetime.now().strftime("%H")) + 3 == int(
        datetime.now(pytz.timezone("Europe/Moscow")).strftime("%H")
    )
    assert int(datetime.now().strftime("%H")) - 3 == int(
        datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%H")
    )
    assert int(datetime.now().strftime("%H")) == int(
        datetime.now(pytz.timezone("Europe/London")).strftime("%H")
    )


def test_get_current_hour_and_utc():
    """Test the final output."""
    assert "Time: " + datetime.now(pytz.timezone("Europe/London")).strftime(
        "%H:%M:%S"
    ) + " UTC+0" == get_locality_time_and_utc("Europe/London")
    assert "Time: " + datetime.now(pytz.timezone("America/Sao_Paulo")).strftime(
        "%H:%M:%S"
    ) + " UTC-3" == get_locality_time_and_utc("America/Sao_Paulo")
    assert "Time: " + datetime.now(pytz.timezone("Europe/Moscow")).strftime(
        "%H:%M:%S"
    ) + " UTC+3" == get_locality_time_and_utc("Europe/Moscow")


def test_get_multiple_zones_time():
    """Test with multiple zones."""
    assert "Europe/London - Time: " + datetime.now(
        pytz.timezone("Europe/London")
    ).strftime("%H:%M:%S") + " " + "UTC+0" + "\n" == get_multiple_zones_time(
        ["Europe/London"]
    )

    assert "Europe/London - Time: " + datetime.now(
        pytz.timezone("Europe/London")
    ).strftime(
        "%H:%M:%S"
    ) + " " + "UTC+0" + "\n" + "America/Sao_Paulo - Time: " + datetime.now(
        pytz.timezone("America/Sao_Paulo")
    ).strftime(
        "%H:%M:%S"
    ) + " " + "UTC-3" + "\n" == get_multiple_zones_time(
        ["Europe/London", "America/Sao_Paulo"]
    )

    assert "Europe/London - Time: " + datetime.now(
        pytz.timezone("Europe/London")
    ).strftime(
        "%H:%M:%S"
    ) + " " + "UTC+0" + "\n" + "America/Sao_Paulo - Time: " + datetime.now(
        pytz.timezone("America/Sao_Paulo")
    ).strftime(
        "%H:%M:%S"
    ) + " " + "UTC-3" + "\n" + "Europe/Moscow - Time: " + datetime.now(
        pytz.timezone("Europe/Moscow")
    ).strftime(
        "%H:%M:%S"
    ) + " " + "UTC+3" + "\n" == get_multiple_zones_time(
        ["Europe/London", "America/Sao_Paulo", "Europe/Moscow"]
    )
