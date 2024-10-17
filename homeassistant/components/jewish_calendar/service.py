"""Services to return HDate instances & other information."""

from __future__ import annotations

import datetime as dt
import logging
from typing import cast

from hdate import HDate, HebrewDate, Zmanim, htables
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LANGUAGE, CONF_LOCATION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_set_service_schema
import homeassistant.util.dt as dt_util
from homeassistant.util.json import JsonObjectType

from .const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DOMAIN,
)

LOGGER = logging.getLogger(__name__)
# Maps Hebrew & English month names to Months enum values.
MONTH_INPUT_MAP = {
    name: htables.Months(index + 1)
    for index, m in enumerate(htables.MONTHS)
    # Require users to specify which Adar they want in case of leap year.
    if m.english != "Adar"
    for name in (m.english, m.hebrew)
}
# Maps Hebrew & English holiday names to Holiday.
HOLIDAY_INPUT_MAP = {
    name: holiday
    for holiday in htables.HOLIDAYS
    for name in (
        holiday.name,
        holiday.description.english,
        holiday.description.hebrew.long,
        holiday.description.hebrew.short,
    )
    if name
}

OUTPUT_SCHEMA = {
    vol.Required("include_hebrew_date_info", default=False): cv.boolean,
    vol.Required("include_holiday_info", default=False): cv.boolean,
    vol.Required("include_zmanim", default=False): cv.boolean,
}

OUTPUT_FIELDS = {
    "include_hebrew_date_info": {"default": True, "selector": {"boolean": {}}},
    "include_holiday_info": {"default": False, "selector": {"boolean": {}}},
    "include_zmanim": {"default": False, "selector": {"boolean": {}}},
}


def async_setup_services(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Register the services."""
    data = hass.data[DOMAIN][config_entry.entry_id]

    location = data[CONF_LOCATION]
    hebrew = data[CONF_LANGUAGE] == "hebrew"
    candle_lighting_offset = data[CONF_CANDLE_LIGHT_MINUTES]
    havdalah_offset = data[CONF_HAVDALAH_OFFSET_MINUTES]
    diaspora = data[CONF_DIASPORA]

    async def get_gregorian_date(call: ServiceCall) -> ServiceResponse:
        """Service call that returns Hebrew date info for a Gregorian date."""
        return build_response(
            HDate(
                resolve_date_param(call),
                diaspora=diaspora,
                hebrew=hebrew,
            ),
            call,
        )

    async def get_gregorian_date_range(call: ServiceCall) -> ServiceResponse:
        """Service call that returns Hebrew date info for a range of Gregorian dates."""
        start = resolve_date_param(call)
        return {
            "dates": [
                build_response(
                    HDate(
                        start + dt.timedelta(days=i),
                        diaspora=diaspora,
                        hebrew=hebrew,
                    ),
                    call,
                )
                for i in range(call.data["number_of_days"])
            ]
        }

    async def get_hebrew_date(call: ServiceCall) -> ServiceResponse:
        """Service call that returns Hebrew date info for a Hebrew date."""
        today: HebrewDate = cast(HebrewDate, HDate(dt_util.now()).hdate)

        date = HDate(
            heb_date=HebrewDate(
                call.data.get("year", today.year),
                call.data["month"],
                call.data["day"],
            ),
            diaspora=diaspora,
            hebrew=hebrew,
        )
        # If the user passed Adar II in a non-leap year, reset to Adar.
        # The HDate implementation treats ADAR_I as ADAR and ADAR_II as
        # 30 days later.  This breaks ADAR_II in non-leap years.
        if date.year_size() < 380 and call.data["month"] in [
            htables.Months.ADAR_I,
            htables.Months.ADAR_II,
        ]:
            date.hdate = HebrewDate(
                call.data.get("year", today.year),
                htables.Months.ADAR,
                call.data["day"],
            )
        return build_response(date, call)

    async def get_holidays(call: ServiceCall) -> ServiceResponse:
        """Service call that returns Hebrew date info for a holiday in a given year."""
        date = get_day_in_year(call)
        holidays = None
        if call.data.get("holidays"):
            holidays = call.data["holidays"]
            types = [holiday.type for holiday in holidays]
        else:
            types = call.data.get("types", [])
        results = date.get_holidays_for_year(types)
        return {
            "holidays": [
                build_response(hdateInfo, call)
                for holiday, hdateInfo in results
                if not holidays or holiday in holidays
            ]
        }

    async def get_next_holiday(call: ServiceCall) -> ServiceResponse:
        """Service call that returns Hebrew date info for a holiday in a given year."""
        date = resolve_date_param(call)
        hdateInfo = HDate(
            date,
            diaspora=diaspora,
            hebrew=hebrew,
        )
        types = call.data.get("types", [])
        while True:
            results = hdateInfo.get_holidays_for_year(types)
            results.sort(key=lambda x: x[1])
            results = [holDate for holiday, holDate in results if holDate >= hdateInfo]
            if results:
                break
            # If we found nothing this year, wrap around to next year.
            hdateInfo = HDate(
                heb_date=HebrewDate(cast(HebrewDate, hdateInfo.hdate).year + 1, 1, 1),
                diaspora=diaspora,
                hebrew=hebrew,
            )

        return build_response(results[0], call)

    def get_day_in_year(call: ServiceCall) -> HDate:
        """Get the HDate in the user-specified year, defaulting to this year."""
        return HDate(
            # If the user specified a year, use that year.
            gdate=None if call.data.get("year") else dt_util.now(),
            heb_date=(
                HebrewDate(call.data["year"], 1, 1) if call.data.get("year") else None
            ),
            diaspora=diaspora,
            hebrew=hebrew,
        )

    def build_response(hdateInfo: HDate, call: ServiceCall) -> JsonObjectType:
        """Build a response for a service call."""
        hdate = cast(HebrewDate, hdateInfo.hdate)

        result: JsonObjectType = {
            "date": cast(dt.date, hdateInfo.gdate).isoformat(),
        }

        if call.data.get("include_hebrew_date_info"):
            result.update(
                {
                    "hebrew_date": {
                        "str": hdateInfo.hebrew_date,
                        "year": hdate.year,
                        "month_name": htables.MONTHS[hdate.month.value - 1]._asdict(),
                        "day": hdate.day,
                    },
                    "day_of_week": hdateInfo.dow,
                    # Additional information
                    "daf_yomi": {
                        "label": hdateInfo.daf_yomi,
                        "mesechta": hdateInfo.daf_yomi_repr[0].name._asdict(),
                        "daf": hdateInfo.daf_yomi_repr[1],
                    },
                    "parasha": htables.PARASHAOT[hdateInfo.get_reading()]._asdict(),
                    "omer_day": hdateInfo.omer_day,
                    "is_yom_tov": hdateInfo.is_yom_tov,
                    "is_shabbat": hdateInfo.is_shabbat,
                    "upcoming_shabbat": cast(
                        dt.date, hdateInfo.upcoming_shabbat.gdate
                    ).isoformat(),
                    "upcoming_yom_tov": cast(
                        dt.date, hdateInfo.upcoming_yom_tov.gdate
                    ).isoformat(),
                    "upcoming_shabbat_or_yom_tov": cast(
                        dt.date, hdateInfo.upcoming_shabbat_or_yom_tov.gdate
                    ).isoformat(),
                }
            )
        if call.data.get("include_holiday_info"):
            result.update(
                {
                    "is_yom_tov": hdateInfo.is_yom_tov,
                    "is_shabbat": hdateInfo.is_shabbat,
                    "holiday_name": hdateInfo.holiday_name,
                    "holiday_type": hdateInfo.holiday_type.name,
                    "holiday_description": hdateInfo.holiday_description,
                    "first_day": cast(dt.date, hdateInfo.first_day.gdate).isoformat(),
                    "last_day": cast(dt.date, hdateInfo.last_day.gdate).isoformat(),
                }
            )
        if call.data.get("include_zmanim"):
            zmanim = Zmanim(
                hdateInfo.gdate,
                candle_lighting_offset=candle_lighting_offset,
                havdalah_offset=havdalah_offset,
                location=location,
            )
            result["zmanim"] = {
                key: value.isoformat() for key, value in zmanim.zmanim.items()
            }
        return result

    def resolve_date_param(call: ServiceCall) -> dt.date:
        """Parse a date from a service's parameters into a date object."""
        if not call.data.get("date"):
            return dt_util.now().date()

        date: dt.datetime = call.data["date"]

        zmanim = Zmanim(
            date,
            location=location,
        )
        if date.astimezone(date.tzinfo) > zmanim.zmanim["sunset"].astimezone(
            date.tzinfo
        ):
            return date.date() + dt.timedelta(days=1)
        return date.date()

    YEAR_FIELD = {"example": 5780, "selector": {"number": {"mode": "box"}}}
    DATE_FIELD = {
        "example": "2023-01-01",
        "selector": {"date": {}},
    }
    TYPES_FIELD = {
        "selector": {
            "select": {
                "multiple": True,
                "options": list(htables.HolidayTypes.__members__.keys()),
            }
        }
    }
    month_names = [
        month.hebrew if hebrew else month.english
        for month in htables.MONTHS
        # Require users to specify which Adar they want in case of leap year.
        if month.english != "Adar"
    ]
    holiday_names = [
        e
        for h in htables.HOLIDAYS
        for e in (
            h.name,
            h.description.hebrew.long if hebrew else h.description.english,
        )
    ]

    hass.services.async_register(
        DOMAIN,
        "get_gregorian_date",
        get_gregorian_date,
        schema=vol.Schema(
            {
                vol.Optional("date"): cv.datetime,
                **OUTPUT_SCHEMA,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        "get_gregorian_date",
        {
            "fields": {
                "date": DATE_FIELD,
                **OUTPUT_FIELDS,
            },
        },
    )

    hass.services.async_register(
        DOMAIN,
        "get_gregorian_date_range",
        get_gregorian_date_range,
        schema=vol.Schema(
            {
                vol.Optional("date"): cv.datetime,
                vol.Required("number_of_days"): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
                **OUTPUT_SCHEMA,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        "get_gregorian_date_range",
        {
            "fields": {
                "date": DATE_FIELD,
                "number_of_days": {
                    "example": 3,
                    "required": True,
                    "selector": {"number": {"min": 1, "mode": "box"}},
                },
                **OUTPUT_FIELDS,
            },
        },
    )

    hass.services.async_register(
        DOMAIN,
        "get_hebrew_date",
        get_hebrew_date,
        schema=vol.Schema(
            {
                vol.Optional("year"): vol.Coerce(int),
                vol.Required("month"): vol.All(
                    vol.In(MONTH_INPUT_MAP.keys()), MONTH_INPUT_MAP.get
                ),
                vol.Required("day"): vol.Coerce(int),
                **OUTPUT_SCHEMA,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        "get_hebrew_date",
        {
            "fields": {
                "year": YEAR_FIELD,
                "month": {
                    "example": month_names[0],
                    "required": True,
                    "selector": {"select": {"options": month_names}},
                },
                "day": {
                    "example": 1,
                    "required": True,
                    "selector": {"number": {"min": 1, "max": 30, "mode": "box"}},
                },
                **OUTPUT_FIELDS,
            },
        },
    )

    hass.services.async_register(
        DOMAIN,
        "get_holidays",
        get_holidays,
        schema=vol.Schema(
            vol.Or(
                {
                    vol.Optional("year"): vol.Coerce(int),
                    vol.Optional("holidays"): vol.All(
                        cv.ensure_list,
                        [vol.In(HOLIDAY_INPUT_MAP.keys())],
                        [HOLIDAY_INPUT_MAP.get],
                    ),
                    **OUTPUT_SCHEMA,
                },
                {
                    vol.Optional("year"): vol.Coerce(int),
                    vol.Optional("types"): vol.All(
                        cv.ensure_list,
                        [cv.enum(htables.HolidayTypes)],
                    ),
                    **OUTPUT_SCHEMA,
                },
            )
        ),
        supports_response=SupportsResponse.ONLY,
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        "get_holidays",
        {
            "fields": {
                "year": YEAR_FIELD,
                "types": TYPES_FIELD,
                "holidays": {
                    "selector": {
                        "select": {
                            "multiple": True,
                            "options": holiday_names,
                        }
                    }
                },
                **OUTPUT_FIELDS,
            },
        },
    )

    hass.services.async_register(
        DOMAIN,
        "get_next_holiday",
        get_next_holiday,
        schema=vol.Schema(
            {
                vol.Optional("date"): cv.datetime,
                vol.Optional("types"): vol.All(
                    cv.ensure_list,
                    [cv.enum(htables.HolidayTypes)],
                ),
                **OUTPUT_SCHEMA,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    async_set_service_schema(
        hass,
        DOMAIN,
        "get_next_holiday",
        {
            "fields": {
                "date": DATE_FIELD,
                "types": TYPES_FIELD,
                **OUTPUT_FIELDS,
            },
        },
    )
