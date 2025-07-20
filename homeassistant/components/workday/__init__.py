"""Sensor to indicate whether the current day is a workday."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import cast

from holidays import PUBLIC, DateLike, HolidayBase, country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_ADD_HOLIDAYS,
    CONF_CATEGORY,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .util import validate_dates

type WorkdayConfigEntry = ConfigEntry[HolidayBase]


async def _async_validate_country_and_province(
    hass: HomeAssistant,
    entry: WorkdayConfigEntry,
    country: str | None,
    province: str | None,
) -> None:
    """Validate country and province."""

    if not country:
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
            "bad_country",
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key="bad_country",
            translation_placeholders={"title": entry.title},
            data={"entry_id": entry.entry_id, "country": None},
        )
        raise ConfigEntryError(f"Selected country {country} is not valid") from ex

    if not province:
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
            "bad_province",
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.ERROR,
            translation_key="bad_province",
            translation_placeholders={
                CONF_COUNTRY: country,
                "title": entry.title,
            },
            data={"entry_id": entry.entry_id, "country": country},
        )
        raise ConfigEntryError(
            f"Selected province {province} for country {country} is not valid"
        ) from ex


def _get_obj_holidays(
    country: str | None,
    province: str | None,
    year: int,
    language: str | None,
    categories: list[str] | None,
) -> HolidayBase:
    """Get the object for the requested country and year."""
    if not country:
        return HolidayBase()

    set_categories = None
    if categories:
        category_list = [PUBLIC]
        category_list.extend(categories)
        set_categories = tuple(category_list)

    obj_holidays: HolidayBase = country_holidays(
        country,
        subdiv=province,
        years=[year, year + 1],
        language=language,
        categories=set_categories,
    )

    supported_languages = obj_holidays.supported_languages
    default_language = obj_holidays.default_language

    if default_language and not language:
        # If no language is set, use the default language
        LOGGER.debug("Changing language from None to %s", default_language)
        return country_holidays(  # Return default if no language
            country,
            subdiv=province,
            years=year,
            language=default_language,
            categories=set_categories,
        )

    if (
        default_language
        and language
        and language not in supported_languages
        and language.startswith("en")
    ):
        # If language does not match supported languages, use the first English variant
        if default_language.startswith("en"):
            LOGGER.debug("Changing language from %s to %s", language, default_language)
            return country_holidays(  # Return default English if default language
                country,
                subdiv=province,
                years=year,
                language=default_language,
                categories=set_categories,
            )
        for lang in supported_languages:
            if lang.startswith("en"):
                LOGGER.debug("Changing language from %s to %s", language, lang)
                return country_holidays(
                    country,
                    subdiv=province,
                    years=year,
                    language=lang,
                    categories=set_categories,
                )

    if default_language and language and language not in supported_languages:
        # If language does not match supported languages, use the default language
        LOGGER.debug("Changing language from %s to %s", language, default_language)
        return country_holidays(  # Return default English if default language
            country,
            subdiv=province,
            years=year,
            language=default_language,
            categories=set_categories,
        )

    return obj_holidays


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
                        is_fixable=True,
                        is_persistent=False,
                        severity=IssueSeverity.WARNING,
                        translation_key="bad_date_holiday",
                        translation_placeholders={
                            CONF_COUNTRY: country if country else "-",
                            "title": entry.title,
                            CONF_REMOVE_HOLIDAYS: remove_holiday,
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
                    is_fixable=True,
                    is_persistent=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="bad_named_holiday",
                    translation_placeholders={
                        CONF_COUNTRY: country if country else "-",
                        "title": entry.title,
                        CONF_REMOVE_HOLIDAYS: remove_holiday,
                    },
                    data={
                        "entry_id": entry.entry_id,
                        "country": country,
                        "named_holiday": remove_holiday,
                    },
                )


async def async_setup_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    calc_add_holidays = cast(
        list[DateLike], validate_dates(entry.options[CONF_ADD_HOLIDAYS])
    )
    calc_remove_holidays: list[str] = validate_dates(
        entry.options[CONF_REMOVE_HOLIDAYS]
    )
    categories: list[str] | None = entry.options.get(CONF_CATEGORY)
    country: str | None = entry.options.get(CONF_COUNTRY)
    days_offset: int = int(entry.options[CONF_OFFSET])
    language: str | None = entry.options.get(CONF_LANGUAGE)
    province: str | None = entry.options.get(CONF_PROVINCE)
    year: int = (dt_util.now() + timedelta(days=days_offset)).year

    await _async_validate_country_and_province(hass, entry, country, province)

    entry.runtime_data = _get_obj_holidays(
        country, province, year, language, categories
    )

    add_remove_custom_holidays(
        hass, entry, country, calc_add_holidays, calc_remove_holidays
    )

    LOGGER.debug("Found the following holidays for your configuration:")
    for holiday_date, name in sorted(entry.runtime_data.items()):
        # Make explicit str variable to avoid "Incompatible types in assignment"
        _holiday_string = holiday_date.strftime("%Y-%m-%d")
        LOGGER.debug("%s %s", _holiday_string, name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Unload Workday config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
