"""The sensibo component."""
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

ALL = ["all"]
SENSIBO_API_TIMEOUT = 10


def ensure_unique_api_keys(value):
    """Validate that each API key is unique across configs."""
    vol.Schema(vol.Unique("duplicate API keys found"))(
        [entry[CONF_API_KEY] for entry in value]
    )
    return value


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, [cv.string]),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [DATA_SCHEMA], ensure_unique_api_keys,)},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Sensibo integration from legacy config file."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config.copy(),
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Sensibo."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "climate")
    )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Sensibo."""
    return await hass.config_entries.async_forward_entry_unload(entry, "climate")
