"""Support for Streamlabs Water Monitor devices."""

from streamlabswater.streamlabswater import StreamlabsClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import StreamlabsConfigEntry, StreamlabsCoordinator

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=streamlabswater"}


PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: StreamlabsConfigEntry) -> bool:
    """Set up StreamLabs from a config entry."""

    api_key = entry.data[CONF_API_KEY]
    client = StreamlabsClient(api_key)
    coordinator = StreamlabsCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: StreamlabsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
