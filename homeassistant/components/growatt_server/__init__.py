"""The Growatt server PV inverter sensor integration."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN, CONF_PLANT_ID


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                        vol.Optional(CONF_NAME): cv.string,
                        vol.Optional(CONF_PLANT_ID): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up this integration."""
    if DOMAIN in config:
        for device in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data=device,
                )
            )
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: config_entries.ConfigEntry):
    """Load the saved entities."""

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
