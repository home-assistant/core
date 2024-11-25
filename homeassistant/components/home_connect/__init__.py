"""Support for BSH Home Connect appliances."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from requests import HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import api
from .const import (
    ATTR_KEY,
    ATTR_PROGRAM,
    ATTR_UNIT,
    ATTR_VALUE,
    BSH_PAUSE,
    BSH_RESUME,
    DOMAIN,
    OLD_NEW_UNIQUE_ID_SUFFIX_MAP,
    SERVICE_OPTION_ACTIVE,
    SERVICE_OPTION_SELECTED,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SELECT_PROGRAM,
    SERVICE_SETTING,
    SERVICE_START_PROGRAM,
)

type HomeConnectConfigEntry = ConfigEntry[api.ConfigEntryAuth]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SETTING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
    }
)

SERVICE_OPTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
        vol.Optional(ATTR_UNIT): str,
    }
)

SERVICE_PROGRAM_SCHEMA = vol.Any(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM): str,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(int, str),
        vol.Optional(ATTR_UNIT): str,
    },
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM): str,
    },
)

SERVICE_COMMAND_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): str})

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


def _get_appliance(
    hass: HomeAssistant,
    device_id: str | None = None,
    device_entry: dr.DeviceEntry | None = None,
    entry: HomeConnectConfigEntry | None = None,
) -> api.HomeConnectAppliance:
    """Return a Home Connect appliance instance given a device id or a device entry."""
    if device_id is not None and device_entry is None:
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device_id)
    assert device_entry, "Either a device id or a device entry must be provided"

    ha_id = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    assert ha_id

    def find_appliance(
        entry: HomeConnectConfigEntry,
    ) -> api.HomeConnectAppliance | None:
        for device in entry.runtime_data.devices:
            appliance = device.appliance
            if appliance.haId == ha_id:
                return appliance
        return None

    if entry is None:
        for entry_id in device_entry.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            assert entry
            if entry.domain == DOMAIN:
                entry = cast(HomeConnectConfigEntry, entry)
                if (appliance := find_appliance(entry)) is not None:
                    return appliance
    elif (appliance := find_appliance(entry)) is not None:
        return appliance
    raise ValueError(f"Appliance for device id {device_entry.id} not found")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Home Connect component."""

    async def _async_service_program(call, method):
        """Execute calls to services taking a program."""
        program = call.data[ATTR_PROGRAM]
        device_id = call.data[ATTR_DEVICE_ID]

        options = []

        option_key = call.data.get(ATTR_KEY)
        if option_key is not None:
            option = {ATTR_KEY: option_key, ATTR_VALUE: call.data[ATTR_VALUE]}

            option_unit = call.data.get(ATTR_UNIT)
            if option_unit is not None:
                option[ATTR_UNIT] = option_unit

            options.append(option)

        appliance = _get_appliance(hass, device_id)
        await hass.async_add_executor_job(getattr(appliance, method), program, options)

    async def _async_service_command(call, command):
        """Execute calls to services executing a command."""
        device_id = call.data[ATTR_DEVICE_ID]

        appliance = _get_appliance(hass, device_id)
        await hass.async_add_executor_job(appliance.execute_command, command)

    async def _async_service_key_value(call, method):
        """Execute calls to services taking a key and value."""
        key = call.data[ATTR_KEY]
        value = call.data[ATTR_VALUE]
        unit = call.data.get(ATTR_UNIT)
        device_id = call.data[ATTR_DEVICE_ID]

        appliance = _get_appliance(hass, device_id)
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


async def async_setup_entry(hass: HomeAssistant, entry: HomeConnectConfigEntry) -> bool:
    """Set up Home Connect from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    entry.runtime_data = api.ConfigEntryAuth(hass, entry, implementation)

    await update_all_devices(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@Throttle(SCAN_INTERVAL)
async def update_all_devices(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> None:
    """Update all the devices."""
    hc_api = entry.runtime_data

    try:
        await hass.async_add_executor_job(hc_api.get_devices)
        for device in hc_api.devices:
            await hass.async_add_executor_job(device.initialize)
    except HTTPError as err:
        _LOGGER.warning("Cannot update devices: %s", err.response.status_code)


async def async_migrate_entry(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1 and entry.minor_version == 1:

        @callback
        def update_unique_id(
            entity_entry: RegistryEntry,
        ) -> dict[str, Any] | None:
            """Update unique ID of entity entry."""
            for old_id_suffix, new_id_suffix in OLD_NEW_UNIQUE_ID_SUFFIX_MAP.items():
                if entity_entry.unique_id.endswith(f"-{old_id_suffix}"):
                    return {
                        "new_unique_id": entity_entry.unique_id.replace(
                            old_id_suffix, new_id_suffix
                        )
                    }
            return None

        await async_migrate_entries(hass, entry.entry_id, update_unique_id)

        hass.config_entries.async_update_entry(entry, minor_version=2)

    _LOGGER.debug("Migration to version %s successful", entry.version)
    return True


def get_dict_from_home_connect_error(err: api.HomeConnectError) -> dict[str, Any]:
    """Return a dict from a Home Connect error."""
    return {
        "description": cast(dict[str, Any], err.args[0]).get("description", "?")
        if len(err.args) > 0 and isinstance(err.args[0], dict)
        else err.args[0]
        if len(err.args) > 0 and isinstance(err.args[0], str)
        else "?",
    }
