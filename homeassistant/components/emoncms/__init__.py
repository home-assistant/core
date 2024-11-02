"""The emoncms component."""

from pyemoncms import EmoncmsClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, EMONCMS_UUID_DOC_URL, LOGGER
from .coordinator import EmoncmsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EmonCMSConfigEntry = ConfigEntry[EmoncmsCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EmonCMSConfigEntry) -> bool:
    """Load a config entry."""
    emoncms_client = EmoncmsClient(
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )
    coordinator = EmoncmsCoordinator(hass, emoncms_client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    url = config_entry.data[CONF_URL]
    LOGGER.debug(
        "Migrating configuration of emoncms server %s from version %s.%s",
        url,
        config_entry.version,
        config_entry.minor_version,
    )
    emoncms_client = EmoncmsClient(
        url,
        config_entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )
    emoncms_unique_id = await emoncms_client.async_get_uuid()

    if config_entry.version == 1:
        if emoncms_unique_id is None:
            # we raise issue and stay on version 1
            async_create_issue(
                hass,
                DOMAIN,
                "migrate database",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="migrate_database",
                translation_placeholders={"url": url, "doc_url": EMONCMS_UUID_DOC_URL},
            )
            status = "not achieved as emoncms has to be updated to a newer version"
        else:
            # we can migrate to version 2
            hass.config_entries.async_update_entry(
                config_entry,
                data=config_entry.data,
                unique_id=emoncms_unique_id,
                minor_version=1,
                version=2,
            )
            status = "successful"
        LOGGER.debug(
            "Migration of emoncms server %s to configuration version %s.%s %s",
            url,
            config_entry.version,
            config_entry.minor_version,
            status,
        )

    return True
