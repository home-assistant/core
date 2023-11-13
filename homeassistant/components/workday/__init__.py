"""Sensor to indicate whether the current day is a workday."""
from __future__ import annotations

from holidays import HolidayBase, country_holidays, list_supported_countries

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_COUNTRY, CONF_PROVINCE, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    country: str | None = entry.options.get(CONF_COUNTRY)
    province: str | None = entry.options.get(CONF_PROVINCE)

    if country and CONF_LANGUAGE not in entry.options:
        cls: HolidayBase = country_holidays(country, subdiv=province)
        default_language = cls.default_language
        new_options = entry.options.copy()
        new_options[CONF_LANGUAGE] = default_language
        hass.config_entries.async_update_entry(entry, options=new_options)

    if country and country not in list_supported_countries():
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
        raise ConfigEntryError(f"Selected country {country} is not valid")

    if country and province and province not in list_supported_countries()[country]:
        async_create_issue(
            hass,
            DOMAIN,
            "bad_province",
            is_fixable=True,
            is_persistent=True,
            severity=IssueSeverity.ERROR,
            translation_key="bad_province",
            translation_placeholders={CONF_COUNTRY: country, "title": entry.title},
            data={"entry_id": entry.entry_id, "country": country},
        )
        raise ConfigEntryError(
            f"Selected province {province} for country {country} is not valid"
        )

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener for options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Workday config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
