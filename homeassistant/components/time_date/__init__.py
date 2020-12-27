"""The time_date component."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the proximity environment."""
    hass.data.setdefault(DOMAIN, {})

    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")
        return False

    if config.get(DOMAIN) is None:
        return True

    # Import configuration from sensor platform
    config_platform = config_per_platform(config, "sensor")
    for p_type, p_config in config_platform:
        if p_type != DOMAIN:
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=p_config,
            )
        )

    return True


async def async_setup_entry(
    hass: HomeAssistantType, entry: config_entries.ConfigEntry
) -> bool:
    """Set the config entry up."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(
    hass: HomeAssistantType, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
