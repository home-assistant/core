"""The FMI (Finnish Meteorological Institute) component."""

from datetime import date, datetime

from dateutil import tz

from homeassistant.const import SUN_EVENT_SUNSET
from homeassistant.helpers.sun import get_astral_event_date

from .const import FMI_WEATHER_SYMBOL_MAP


def get_weather_symbol(symbol, hass=None):
    """Get a weather symbol for the symbol value."""

    if hass is not None and symbol == 1:  # Clear as per FMI
        today = date.today()
        sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)
        sunset = sunset.astimezone(tz.tzlocal())

        if datetime.now().astimezone(tz.tzlocal()) >= sunset:
            # Clear night
            return FMI_WEATHER_SYMBOL_MAP.get(0, "")

    return FMI_WEATHER_SYMBOL_MAP.get(symbol, "")
