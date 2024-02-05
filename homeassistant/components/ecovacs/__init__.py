"""Support for Ecovacs Deebot vacuums."""
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CONTINENT, DOMAIN
from .controller import EcovacsController

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_COUNTRY): vol.All(vol.Lower, cv.string),
                vol.Required(CONF_CONTINENT): vol.All(vol.Lower, cv.string),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ecovacs component."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    controller = EcovacsController(hass, entry.data)
    await controller.initialize()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].teardown()
        hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return unload_ok
