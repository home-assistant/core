"""Component to integrate with Sinch SMS API."""

from clx.xms.exceptions import UnauthorizedException, UnexpectedResponseException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, CONF_SENDER, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .config_flow import check_client_connection
from .const import (
    ATTR_OPTIONS,
    CONF_DEFAULT_RECIPIENTS,
    CONF_SERVICE_PLAN_ID,
    DEFAULT_SENDER,
    DOMAIN,
)

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

DEFAULT_OPTIONS = {
    CONF_SENDER: DEFAULT_SENDER,
    CONF_DEFAULT_RECIPIENTS: [],
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sinch SMS component."""

    if Platform.NOTIFY in config:
        for entry in config[Platform.NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )
    return True


@callback
def _async_migrate_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    data = dict(entry.data)
    options = dict(entry.options)

    if list(options) != list(DEFAULT_OPTIONS):
        options = dict(DEFAULT_OPTIONS, **options)
        options[CONF_DEFAULT_RECIPIENTS] = data.pop(CONF_DEFAULT_RECIPIENTS, [])
        options[CONF_SENDER] = data.pop(CONF_SENDER, DEFAULT_SENDER)

        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Sinch SMS from a config entry."""

    _async_migrate_options_from_data_if_missing(hass, config_entry)
    try:
        await hass.async_add_executor_job(
            check_client_connection,
            config_entry.data[CONF_SERVICE_PLAN_ID],
            config_entry.data[CONF_API_KEY],
        )
    except (UnauthorizedException, UnexpectedResponseException) as ex:
        raise ConfigEntryNotReady(
            f"Failed to connect to sinch using service plan: {config_entry.data[CONF_SERVICE_PLAN_ID]}"
        ) from ex

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = config_entry.data | {
        ATTR_OPTIONS: config_entry.options
    }
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id],
            hass.data[DOMAIN],
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
