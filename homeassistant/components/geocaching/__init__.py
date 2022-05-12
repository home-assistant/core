"""The Geocaching integration."""
import voluptuous as vol

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .config_flow import GeocachingFlowHandler
from .const import DOMAIN
from .coordinator import GeocachingDataUpdateCoordinator
from .oauth import GeocachingOAuth2Implementation

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Geocaching component."""
    if DOMAIN not in config:
        return True

    GeocachingFlowHandler.async_register_implementation(
        hass,
        GeocachingOAuth2Implementation(
            hass,
            client_id=config[DOMAIN][CONF_CLIENT_ID],
            client_secret=config[DOMAIN][CONF_CLIENT_SECRET],
            name="Geocaching",
        ),
    )

    # When manual configuration is done, discover the integration.
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Geocaching from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    oauth_session = OAuth2Session(hass, entry, implementation)
    coordinator = GeocachingDataUpdateCoordinator(
        hass, entry=entry, session=oauth_session
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
