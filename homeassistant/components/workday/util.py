"""Helpers functions for the Workday component."""

from collections.abc import Mapping
from datetime import date, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from holidays import PUBLIC, DateLike, HolidayBase, country_holidays

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util import dt as dt_util, slugify

from .const import COUNTRY_OPTIONS, DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import WorkdayConfigEntry


async def async_validate_country_and_province(
    hass: HomeAssistant,
    entry: WorkdayConfigEntry,
    country: str | None,
    province: str | None,
) -> None:
    """Validate country and province."""
    bad_country_issue_id = f"bad_country-{entry.entry_id}"
    bad_province_issue_id = f"bad_province-{entry.entry_id}"

    if not country:
        async_delete_issue(hass, DOMAIN, bad_country_issue_id)
        async_delete_issue(hass, DOMAIN, bad_province_issue_id)
        return
    try:
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            # import executor job is used here because multiple integrations use
            # the holidays library and it is not thread safe to import it in parallel
            # https://github.com/python/cpython/issues/83065
            await hass.async_add_import_executor_job(country_holidays, country)
    except NotImplementedError as ex:
        async_create_issue(
            hass,
            DOMAIN,
            bad_country_issue_id,
            config_entry_id=entry.entry_id,
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key="bad_country",
            translation_placeholders={"title": entry.title},
            data={"entry_id": entry.entry_id, "country": None},
        )
        raise ConfigEntryError(f"Selected country {country} is not valid") from ex
    async_delete_issue(hass, DOMAIN, bad_country_issue_id)

    if not province:
        async_delete_issue(hass, DOMAIN, bad_province_issue_id)
        return
    try:
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            # import executor job is used here because multiple integrations use
            # the holidays library and it is not thread safe to import it in parallel
            # https://github.com/python/cpython/issues/83065
            await hass.async_add_import_executor_job(
                partial(country_holidays, country, subdiv=province)
            )
    except NotImplementedError as ex:
        async_create_issue(
            hass,
            DOMAIN,
            bad_province_issue_id,
            config_entry_id=entry.entry_id,
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key="bad_province",
            translation_placeholders={
                "country": country,
                "title": entry.title,
            },
            data={"entry_id": entry.entry_id, "country": country},
        )
        raise ConfigEntryError(
            f"Selected province {province} for country {country} is not valid"
        ) from ex
    async_delete_issue(hass, DOMAIN, bad_province_issue_id)


def validate_dates(holiday_list: list[str]) -> list[str]:
    """Validate and add to list of dates to add or remove."""
    calc_holidays: list[str] = []
    for add_date in holiday_list:
        if add_date.find(",") > 0:
            dates = add_date.split(",", maxsplit=1)
            d1 = dt_util.parse_date(dates[0])
            d2 = dt_util.parse_date(dates[1])
            if d1 is None or d2 is None:
                LOGGER.error("Incorrect dates in date range: %s", add_date)
                continue
            _range: timedelta = d2 - d1
            for i in range(_range.days + 1):
                day: date = d1 + timedelta(days=i)
                calc_holidays.append(day.strftime("%Y-%m-%d"))
            continue
        calc_holidays.append(add_date)
    return calc_holidays


def _get_language(entity: HolidayBase, language: str | None) -> str | None:
    """Return the supported language that is closest to the requested language."""
    if not (default_language := entity.default_language):
        return language
    if not language:
        return default_language
    supported_languages = entity.supported_languages
    if language in supported_languages:
        return language
    if language.startswith("en"):
        if default_language.startswith("en"):
            return default_language
        for supported_language in supported_languages:
            if supported_language.startswith("en"):
                return supported_language
    return default_language


def get_holidays_object(
    country: str | None,
    province: str | None,
    year: int,
    language: str | None,
    categories: list[str] | None,
    options: Mapping[str, Any],
) -> HolidayBase:
    """Get the object for the requested country and year."""
    if not country:
        return HolidayBase()

    # Without years, no holidays are calculated, but the metadata is available
    entity = country_holidays(country)
    if (holidays_language := _get_language(entity, language)) != language:
        LOGGER.debug("Changing language from %s to %s", language, holidays_language)

    # A repair can change the country, and the library raises on unsupported options
    supported_options = entity.get_supported_options()
    return country_holidays(
        country,
        subdiv=province,
        years=[year, year + 1],
        language=holidays_language,
        categories=(PUBLIC, *categories) if categories else None,
        **{
            option: options[option]
            for option in COUNTRY_OPTIONS
            if option in options and option in supported_options
        },
    )


def add_remove_custom_holidays(
    hass: HomeAssistant,
    entry: WorkdayConfigEntry,
    country: str | None,
    calc_add_holidays: list[DateLike],
    calc_remove_holidays: list[str],
) -> None:
    """Add or remove custom holidays."""
    next_year = dt_util.now().year + 1

    # Add custom holidays
    try:
        entry.runtime_data.append(calc_add_holidays)
    except ValueError as error:
        LOGGER.error("Could not add custom holidays: %s", error)

    # Remove custom holidays
    for remove_holiday in calc_remove_holidays:
        try:
            # is this formatted as a date?
            if dt_util.parse_date(remove_holiday):
                # remove holiday by date
                removed = entry.runtime_data.pop(remove_holiday)
                LOGGER.debug("Removed %s", remove_holiday)
            else:
                # remove holiday by name
                LOGGER.debug("Treating '%s' as named holiday", remove_holiday)
                removed = entry.runtime_data.pop_named(remove_holiday)
                for holiday in removed:
                    LOGGER.debug("Removed %s by name '%s'", holiday, remove_holiday)
        except KeyError as unmatched:
            LOGGER.warning("No holiday found matching %s", unmatched)
            if _date := dt_util.parse_date(remove_holiday):
                if _date.year <= next_year:
                    # Only check and raise issues for max next year
                    async_create_issue(
                        hass,
                        DOMAIN,
                        f"bad_date_holiday-{entry.entry_id}-{slugify(remove_holiday)}",
                        config_entry_id=entry.entry_id,
                        is_fixable=True,
                        is_persistent=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="bad_date_holiday",
                        translation_placeholders={
                            "country": country or "-",
                            "title": entry.title,
                            "remove_holidays": remove_holiday,
                        },
                        data={
                            "entry_id": entry.entry_id,
                            "country": country,
                            "named_holiday": remove_holiday,
                        },
                    )
            else:
                async_create_issue(
                    hass,
                    DOMAIN,
                    f"bad_named_holiday-{entry.entry_id}-{slugify(remove_holiday)}",
                    config_entry_id=entry.entry_id,
                    is_fixable=True,
                    is_persistent=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="bad_named_holiday",
                    translation_placeholders={
                        "country": country or "-",
                        "title": entry.title,
                        "remove_holidays": remove_holiday,
                    },
                    data={
                        "entry_id": entry.entry_id,
                        "country": country,
                        "named_holiday": remove_holiday,
                    },
                )
