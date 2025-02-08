"""Support for BSH Home Connect appliances."""

from __future__ import annotations

import logging
from typing import Any, cast

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import CommandKey, Option, OptionKey, ProgramKey, SettingKey
from aiohomeconnect.model.error import HomeConnectError
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth
from .const import (
    ATTR_KEY,
    ATTR_PROGRAM,
    ATTR_UNIT,
    ATTR_VALUE,
    DOMAIN,
    OLD_NEW_UNIQUE_ID_SUFFIX_MAP,
    SERVICE_OPTION_ACTIVE,
    SERVICE_OPTION_SELECTED,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SELECT_PROGRAM,
    SERVICE_SETTING,
    SERVICE_START_PROGRAM,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_PROGRAM,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
)
from .coordinator import HomeConnectConfigEntry, HomeConnectCoordinator
from .utils import get_dict_from_home_connect_error

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_SETTING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_KEY): vol.All(
            vol.Coerce(SettingKey),
            vol.NotIn([SettingKey.UNKNOWN]),
        ),
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
    }
)

SERVICE_OPTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_KEY): vol.All(
            vol.Coerce(OptionKey),
            vol.NotIn([OptionKey.UNKNOWN]),
        ),
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
        vol.Optional(ATTR_UNIT): str,
    }
)

SERVICE_PROGRAM_SCHEMA = vol.Any(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM): vol.All(
            vol.Coerce(ProgramKey),
            vol.NotIn([ProgramKey.UNKNOWN]),
        ),
        vol.Required(ATTR_KEY): vol.All(
            vol.Coerce(OptionKey),
            vol.NotIn([OptionKey.UNKNOWN]),
        ),
        vol.Required(ATTR_VALUE): vol.Any(int, str),
        vol.Optional(ATTR_UNIT): str,
    },
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM): vol.All(
            vol.Coerce(ProgramKey),
            vol.NotIn([ProgramKey.UNKNOWN]),
        ),
    },
)

SERVICE_COMMAND_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): str})

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def _get_client_and_ha_id(
    hass: HomeAssistant, device_id: str
) -> tuple[HomeConnectClient, str]:
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError("Device entry not found for device id")
    entry: HomeConnectConfigEntry | None = None
    for entry_id in device_entry.config_entries:
        _entry = hass.config_entries.async_get_entry(entry_id)
        assert _entry
        if _entry.domain == DOMAIN:
            entry = cast(HomeConnectConfigEntry, _entry)
            break
    if entry is None:
        raise ServiceValidationError(
            "Home Connect config entry not found for that device id"
        )

    ha_id = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )
    if ha_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="appliance_not_found",
            translation_placeholders={
                "device_id": device_id,
            },
        )
    return entry.runtime_data.client, ha_id


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Home Connect component."""

    async def _async_service_program(call: ServiceCall, start: bool):
        """Execute calls to services taking a program."""
        program = call.data[ATTR_PROGRAM]
        client, ha_id = await _get_client_and_ha_id(hass, call.data[ATTR_DEVICE_ID])

        option_key = call.data.get(ATTR_KEY)
        options = (
            [
                Option(
                    option_key,
                    call.data[ATTR_VALUE],
                    unit=call.data.get(ATTR_UNIT),
                )
            ]
            if option_key is not None
            else None
        )

        try:
            if start:
                await client.start_program(ha_id, program_key=program, options=options)
            else:
                await client.set_selected_program(
                    ha_id, program_key=program, options=options
                )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="start_program" if start else "select_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_PROGRAM: program,
                },
            ) from err

    async def _async_service_set_program_options(call: ServiceCall, active: bool):
        """Execute calls to services taking a program."""
        option_key = call.data[ATTR_KEY]
        value = call.data[ATTR_VALUE]
        unit = call.data.get(ATTR_UNIT)
        client, ha_id = await _get_client_and_ha_id(hass, call.data[ATTR_DEVICE_ID])

        try:
            if active:
                await client.set_active_program_option(
                    ha_id,
                    option_key=option_key,
                    value=value,
                    unit=unit,
                )
            else:
                await client.set_selected_program_option(
                    ha_id,
                    option_key=option_key,
                    value=value,
                    unit=unit,
                )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_options_active_program"
                if active
                else "set_options_selected_program",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_KEY: option_key,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: str(value),
                },
            ) from err

    async def _async_service_command(call: ServiceCall, command_key: CommandKey):
        """Execute calls to services executing a command."""
        client, ha_id = await _get_client_and_ha_id(hass, call.data[ATTR_DEVICE_ID])

        try:
            await client.put_command(ha_id, command_key=command_key, value=True)
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="execute_command",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    "command": command_key.value,
                },
            ) from err

    async def async_service_option_active(call: ServiceCall):
        """Service for setting an option for an active program."""
        await _async_service_set_program_options(call, True)

    async def async_service_option_selected(call: ServiceCall):
        """Service for setting an option for a selected program."""
        await _async_service_set_program_options(call, False)

    async def async_service_setting(call: ServiceCall):
        """Service for changing a setting."""
        key = call.data[ATTR_KEY]
        value = call.data[ATTR_VALUE]
        client, ha_id = await _get_client_and_ha_id(hass, call.data[ATTR_DEVICE_ID])

        try:
            await client.set_setting(ha_id, setting_key=key, value=value)
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_setting",
                translation_placeholders={
                    **get_dict_from_home_connect_error(err),
                    SVE_TRANSLATION_PLACEHOLDER_KEY: key,
                    SVE_TRANSLATION_PLACEHOLDER_VALUE: str(value),
                },
            ) from err

    async def async_service_pause_program(call: ServiceCall):
        """Service for pausing a program."""
        await _async_service_command(call, CommandKey.BSH_COMMON_PAUSE_PROGRAM)

    async def async_service_resume_program(call: ServiceCall):
        """Service for resuming a paused program."""
        await _async_service_command(call, CommandKey.BSH_COMMON_RESUME_PROGRAM)

    async def async_service_select_program(call: ServiceCall):
        """Service for selecting a program."""
        await _async_service_program(call, False)

    async def async_service_start_program(call: ServiceCall):
        """Service for starting a program."""
        await _async_service_program(call, True)

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

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    config_entry_auth = AsyncConfigEntryAuth(hass, session)

    home_connect_client = HomeConnectClient(config_entry_auth)

    coordinator = HomeConnectCoordinator(hass, entry, home_connect_client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.runtime_data.start_event_listener()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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
