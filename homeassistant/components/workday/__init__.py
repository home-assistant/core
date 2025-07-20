"""Sensor to indicate whether the current day is a workday."""

from __future__ import annotations

from datetime import timedelta
from functools import partial

from holidays import PUBLIC, HolidayBase, country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util import dt as dt_util

from .const import CONF_CATEGORY, CONF_OFFSET, CONF_PROVINCE, DOMAIN, LOGGER, PLATFORMS

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


async def async_setup_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    country: str | None = entry.options.get(CONF_COUNTRY)
    province: str | None = entry.options.get(CONF_PROVINCE)
    days_offset: int = int(entry.options[CONF_OFFSET])
    year: int = (dt_util.now() + timedelta(days=days_offset)).year
    language: str | None = entry.options.get(CONF_LANGUAGE)
    categories: list[str] | None = entry.options.get(CONF_CATEGORY)

    await _async_validate_country_and_province(hass, entry, country, province)

    entry.runtime_data = _get_obj_holidays(
        country, province, year, language, categories
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WorkdayConfigEntry) -> bool:
    """Unload Workday config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
