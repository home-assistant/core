"""The Holiday integration."""

from functools import partial
from typing import TYPE_CHECKING

from holidays import country_holidays, list_supported_countries

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import (
    CONF_CATEGORIES,
    CONF_PROVINCE,
    DOMAIN,
    ISSUE_UNSUPPORTED_CATEGORIES,
    ISSUE_UNSUPPORTED_COUNTRY,
    ISSUE_UNSUPPORTED_PROVINCE,
)

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Holiday from a config entry."""
    country: str = entry.data[CONF_COUNTRY]
    province: str | None = entry.data.get(CONF_PROVINCE)
    categories: list[str] | None = entry.options.get(CONF_CATEGORIES)

    # We only import here to ensure that that its not imported later
    # in the event loop since the platforms will call country_holidays
    # which loads python code from disk.
    try:
        with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            # import executor job is used here because multiple integrations use
            # the holidays library and it is not thread safe to import it in parallel
            # https://github.com/python/cpython/issues/83065
            await hass.async_add_import_executor_job(
                partial(
                    country_holidays, country, subdiv=province, categories=categories
                )
            )
    except NotImplementedError as err:
        # The holidays library raises the same error for a country and a province
        if country not in await hass.async_add_executor_job(list_supported_countries):
            _async_raise_unsupported(
                hass, entry, ISSUE_UNSUPPORTED_COUNTRY, {"country": country}, err
            )
        else:
            if TYPE_CHECKING:
                assert province is not None
            _async_raise_unsupported(
                hass,
                entry,
                ISSUE_UNSUPPORTED_PROVINCE,
                {"country": country, "province": province},
                err,
            )
    except ValueError as err:
        _async_raise_unsupported(
            hass,
            entry,
            ISSUE_UNSUPPORTED_CATEGORIES,
            {"country": country, "categories": ", ".join(categories or [])},
            err,
        )

    for issue in (
        ISSUE_UNSUPPORTED_COUNTRY,
        ISSUE_UNSUPPORTED_PROVINCE,
        ISSUE_UNSUPPORTED_CATEGORIES,
    ):
        ir.async_delete_issue(hass, DOMAIN, f"{issue}_{entry.entry_id}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def _async_raise_unsupported(
    hass: HomeAssistant,
    entry: ConfigEntry,
    issue: str,
    placeholders: dict[str, str],
    err: Exception,
) -> None:
    """Create a repair issue and raise for configuration the library no longer supports."""
    placeholders = {"title": entry.title, **placeholders}
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{issue}_{entry.entry_id}",
        config_entry_id=entry.entry_id,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=issue,
        translation_placeholders=placeholders,
        data={"entry_id": entry.entry_id, "issue": issue},
    )
    raise ConfigEntryError(
        translation_domain=DOMAIN,
        translation_key=issue,
        translation_placeholders=placeholders,
    ) from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
