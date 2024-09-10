"""Support for Streamlabs Water Monitor devices."""

from streamlabswater.streamlabswater import StreamlabsClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import StreamlabsCoordinator

ATTR_AWAY_MODE = "away_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
AWAY_MODE_AWAY = "away"
AWAY_MODE_HOME = "home"

CONF_LOCATION_ID = "location_id"

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=streamlabswater"}

SET_AWAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_AWAY_MODE): vol.In([AWAY_MODE_AWAY, AWAY_MODE_HOME]),
        vol.Optional(CONF_LOCATION_ID): cv.string,
    }
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up StreamLabs from a config entry."""

    api_key = entry.data[CONF_API_KEY]
    client = StreamlabsClient(api_key)
    coordinator = StreamlabsCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def set_away_mode(service: ServiceCall) -> None:
        """Set the StreamLabsWater Away Mode."""
        away_mode = service.data.get(ATTR_AWAY_MODE)
        location_id = service.data.get(CONF_LOCATION_ID) or list(coordinator.data)[0]
        client.update_location(location_id, away_mode)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_AWAY_MODE, set_away_mode, schema=SET_AWAY_MODE_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
