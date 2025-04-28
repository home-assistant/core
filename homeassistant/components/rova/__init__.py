"""The rova component."""

from __future__ import annotations

from requests.exceptions import ConnectTimeout, HTTPError
from rova.rova import Rova

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_HOUSE_NUMBER, CONF_HOUSE_NUMBER_SUFFIX, CONF_ZIP_CODE, DOMAIN
from .coordinator import RovaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ROVA from a config entry."""

    api = Rova(
        entry.data[CONF_ZIP_CODE],
        entry.data[CONF_HOUSE_NUMBER],
        entry.data[CONF_HOUSE_NUMBER_SUFFIX],
    )

    try:
        rova_area = await hass.async_add_executor_job(api.is_rova_area)
    except (ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady from ex

    if not rova_area:
        async_create_issue(
            hass,
            DOMAIN,
            f"no_rova_area_{entry.data[CONF_ZIP_CODE]}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.ERROR,
            translation_key="no_rova_area",
            translation_placeholders={
                CONF_ZIP_CODE: entry.data[CONF_ZIP_CODE],
            },
        )
        raise ConfigEntryError("Rova does not collect garbage in this area")

    coordinator = RovaCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ROVA config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
