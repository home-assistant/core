"""Support for BSH Home Connect appliances."""

from datetime import timedelta
import logging
from typing import Optional

from requests import HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import api, config_flow
from .const import (
    ATTR_KEY,
    ATTR_OPTIONS,
    ATTR_PROGRAM,
    ATTR_UNIT,
    ATTR_VALUE,
    BSH_PAUSE,
    BSH_RESUME,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SERVICE_OPTION_ACTIVE,
    SERVICE_OPTION_SELECTED,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SELECT_PROGRAM,
    SERVICE_SETTING,
    SERVICE_START_PROGRAM,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

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


SERVICE_SETTING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
    }
)

SERVICE_OPTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
        vol.Optional(ATTR_UNIT): str,
    }
)

SERVICE_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_PROGRAM): str,
        vol.Optional(ATTR_OPTIONS): [
            {
                vol.Required(ATTR_KEY): str,
                vol.Required(ATTR_VALUE): vol.Any(int, str),
                vol.Optional(ATTR_UNIT): str,
            }
        ],
    }
)

SERVICE_COMMAND_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})


PLATFORMS = ["binary_sensor", "light", "sensor", "switch"]


def _get_appliance_by_entity_id(
    hass: HomeAssistant, entity_id: str
) -> Optional[api.HomeConnectDevice]:
    """Return a Home Connect appliance instance given an entity_id."""
    for hc in hass.data[DOMAIN].values():
        for dev_dict in hc.devices:
            device = dev_dict[CONF_DEVICE]
            for entity in device.entities:
                if entity.entity_id == entity_id:
                    return device.appliance
    _LOGGER.error("Appliance for %s not found.", entity_id)
    return None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Home Connect component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    async def _async_service_program(call, method):
        """Execute calls to services taking a program."""
        program = call.data[ATTR_PROGRAM]
        entity_id = call.data[ATTR_ENTITY_ID]
        options = call.data.get(ATTR_OPTIONS)
        appliance = _get_appliance_by_entity_id(hass, entity_id)
        if appliance is not None:
            await hass.async_add_executor_job(
                getattr(appliance, method), program, options
            )

    async def _async_service_command(call, command):
        """Execute calls to services executing a command."""
        entity_id = call.data[ATTR_ENTITY_ID]
        appliance = _get_appliance_by_entity_id(hass, entity_id)
        if appliance is not None:
            await hass.async_add_executor_job(appliance.execute_command, command)

    async def _async_service_key_value(call, method):
        """Execute calls to services taking a key and value."""
        key = call.data[ATTR_KEY]
        value = call.data[ATTR_VALUE]
        unit = call.data.get(ATTR_UNIT)
        entity_id = call.data[ATTR_ENTITY_ID]
        appliance = _get_appliance_by_entity_id(hass, entity_id)
        if appliance is not None:
            if unit is not None:
                await hass.async_add_executor_job(
                    getattr(appliance, method),
                    key,
                    value,
                    unit,
                )
            else:
                await hass.async_add_executor_job(
                    getattr(appliance, method),
                    key,
                    value,
                )

    async def async_service_option_active(call):
        """Service for setting an option for an active program."""
        await _async_service_key_value(call, "set_options_active_program")

    async def async_service_option_selected(call):
        """Service for setting an option for a selected program."""
        await _async_service_key_value(call, "set_options_selected_program")

    async def async_service_setting(call):
        """Service for changing a setting."""
        await _async_service_key_value(call, "set_setting")

    async def async_service_pause_program(call):
        """Service for pausing a program."""
        await _async_service_command(call, BSH_PAUSE)

    async def async_service_resume_program(call):
        """Service for resuming a paused program."""
        await _async_service_command(call, BSH_RESUME)

    async def async_service_select_program(call):
        """Service for selecting a program."""
        await _async_service_program(call, "select_program")

    async def async_service_start_program(call):
        """Service for starting a program."""
        await _async_service_program(call, "start_program")

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPTION_ACTIVE,
        async_service_option_active,
        schema=SERVICE_OPTION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPTION_SELECTED,
        async_service_option_selected,
        schema=SERVICE_OPTION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SETTING, async_service_setting, schema=SERVICE_SETTING_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAUSE_PROGRAM,
        async_service_pause_program,
        schema=SERVICE_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_PROGRAM,
        async_service_resume_program,
        schema=SERVICE_COMMAND_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SELECT_PROGRAM,
        async_service_select_program,
        schema=SERVICE_PROGRAM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_PROGRAM,
        async_service_start_program,
        schema=SERVICE_PROGRAM_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Connect from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    hc_api = api.ConfigEntryAuth(hass, entry, implementation)

    hass.data[DOMAIN][entry.entry_id] = hc_api

    await update_all_devices(hass, entry)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@Throttle(SCAN_INTERVAL)
async def update_all_devices(hass, entry):
    """Update all the devices."""
    data = hass.data[DOMAIN]
    hc_api = data[entry.entry_id]
    try:
        await hass.async_add_executor_job(hc_api.get_devices)
        for device_dict in hc_api.devices:
            await hass.async_add_executor_job(device_dict["device"].initialize)
    except HTTPError as err:
        _LOGGER.warning("Cannot update devices: %s", err.response.status_code)
