"""Support for Streamlabs Water Monitor devices."""

from streamlabswater.streamlabswater import StreamlabsClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import StreamlabsCoordinator

ATTR_AWAY_MODE = "away_mode"
SERVICE_SET_AWAY_MODE = "set_away_mode"
AWAY_MODE_AWAY = "away"
AWAY_MODE_HOME = "home"

CONF_LOCATION_ID = "location_id"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_LOCATION_ID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SET_AWAY_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_AWAY_MODE): vol.In([AWAY_MODE_AWAY, AWAY_MODE_HOME]),
        vol.Optional(CONF_LOCATION_ID): cv.string,
    }
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the streamlabs water integration."""

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_API_KEY: config[DOMAIN][CONF_API_KEY]},
            )
        )

    return True


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
        location_id = (
            service.data.get(CONF_LOCATION_ID) or list(coordinator.data.values())[0]
        )
        client.update_location(location_id, away_mode)

    hass.services.register(
        DOMAIN, SERVICE_SET_AWAY_MODE, set_away_mode, schema=SET_AWAY_MODE_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
