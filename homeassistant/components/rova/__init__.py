"""The rova component."""

from requests.exceptions import ConnectTimeout, HTTPError
from rova.rova import Rova

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_HOUSE_NUMBER, CONF_HOUSE_NUMBER_SUFFIX, CONF_ZIP_CODE, DOMAIN
from .coordinator import RovaConfigEntry, RovaCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RovaConfigEntry) -> None:
    """Set up ROVA from a config entry."""

    zip_code = entry.data[CONF_ZIP_CODE]
    house_number = entry.data[CONF_HOUSE_NUMBER]
    house_number_suffix = entry.data[CONF_HOUSE_NUMBER_SUFFIX]
    api = Rova(zip_code, house_number, house_number_suffix)

    try:
        rova_area = await hass.async_add_executor_job(api.is_rova_area)
    except (ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady from ex

    if not rova_area:
        async_create_issue(
            hass,
            DOMAIN,
            f"no_rova_area_{entry.entry_id}",
            config_entry_id=entry.entry_id,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.ERROR,
            translation_key="no_rova_area",
            translation_placeholders={
                "address": f"{zip_code} {house_number} {house_number_suffix}".strip(),
            },
        )
        raise ConfigEntryError("Rova does not collect garbage in this area")

    coordinator = RovaCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: RovaConfigEntry) -> None:
    """Unload ROVA config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
