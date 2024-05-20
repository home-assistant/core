"""Sensor to indicate whether the current day is a workday."""

from __future__ import annotations

from functools import partial

from holidays import HolidayBase, country_holidays

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import CONF_PROVINCE, DOMAIN, PLATFORMS


async def _async_validate_country_and_province(
    hass: HomeAssistant, entry: ConfigEntry, country: str | None, province: str | None
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
            is_persistent=True,
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
            is_persistent=True,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    country: str | None = entry.options.get(CONF_COUNTRY)
    province: str | None = entry.options.get(CONF_PROVINCE)

    await _async_validate_country_and_province(hass, entry, country, province)

    if country and CONF_LANGUAGE not in entry.options:
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            # import executor job is used here because multiple integrations use
            # the holidays library and it is not thread safe to import it in parallel
            # https://github.com/python/cpython/issues/83065
            cls: HolidayBase = await hass.async_add_import_executor_job(
                partial(country_holidays, country, subdiv=province)
            )
        default_language = cls.default_language
        new_options = entry.options.copy()
        new_options[CONF_LANGUAGE] = default_language
        hass.config_entries.async_update_entry(entry, options=new_options)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Workday config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
