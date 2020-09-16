"""The econet component."""
from pyeconet.errors import InvalidCredentialsError

from homeassistant.components.econet.common import (
    _LOGGER,
    async_get_api_from_data,
    get_data_api,
    set_data_api,
)
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, base_config: dict) -> bool:
    """Set up component."""

    water_heater_configs = [
        platform_config
        for platform_config in base_config.get(WATER_HEATER_DOMAIN, [])
        if platform_config[CONF_PLATFORM] == DOMAIN
    ]

    for config in water_heater_configs:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_EMAIL: config[CONF_USERNAME],
                    CONF_PASSWORD: config[CONF_PASSWORD],
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up config entry."""

    try:
        api = await async_get_api_from_data(config_entry.data)
        # Perform initial get so the subscribe method below will work correctly.
        await api.get_equipment_by_type([])
    except InvalidCredentialsError:
        _LOGGER.error(
            "Invalid credentials for email: %s", config_entry.data[CONF_EMAIL]
        )
        return False
    except Exception as exception:  # pylint: disable=broad-except
        raise ConfigEntryNotReady from exception

    set_data_api(hass, config_entry, api)

    # Start subscription for data changes.
    await hass.async_add_job(api.subscribe)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, WATER_HEATER_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload config entry."""
    api = get_data_api(hass, config_entry)

    # Stop subscription for data changes.
    await hass.async_add_job(api.unsubscribe)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(
            config_entry, WATER_HEATER_DOMAIN
        )
    )

    return True
