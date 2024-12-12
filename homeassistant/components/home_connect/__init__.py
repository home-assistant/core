"""Support for BSH Home Connect appliances."""

from __future__ import annotations

from datetime import timedelta
import logging
import re
from typing import Any, cast

from requests import HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from . import api
from .const import (
    ATTR_ALLOWED_VALUES,
    ATTR_BSH_KEY,
    ATTR_KEY,
    ATTR_PROGRAM,
    ATTR_UNIT,
    ATTR_VALUE,
    BSH_COMMON_OPTION_DURATION,
    BSH_PAUSE,
    BSH_RESUME,
    DOMAIN,
    OLD_NEW_UNIQUE_ID_SUFFIX_MAP,
    PROGRAM_ENUM_OPTIONS,
    SERVICE_OPTION_ACTIVE,
    SERVICE_OPTION_SELECTED,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SELECT_PROGRAM,
    SERVICE_SETTING,
    SERVICE_START_PROGRAM,
    SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID,
    SVE_TRANSLATION_PLACEHOLDER_KEY,
    SVE_TRANSLATION_PLACEHOLDER_PROGRAM,
    SVE_TRANSLATION_PLACEHOLDER_VALUE,
    TRANSLATION_KEYS_PROGRAMS_MAP,
    bsh_key_to_translation_key,
)

type HomeConnectConfigEntry = ConfigEntry[api.ConfigEntryAuth]

_LOGGER = logging.getLogger(__name__)

RE_CAMEL_CASE = re.compile(r"(?<!^)(?=[A-Z])|(?=\d)(?<=\D)")

SCAN_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


ATTR_SCHEMA = "schema"
ATTR_CUSTOM_OPTIONS = "custom_options"
ATTR_START = "start"
ATTR_FORCE_SELECTED_ACTIVE = "force_selected_active"

OPTION_COFFEE_MILK_RATIO = "ConsumerProducts.CoffeeMaker.Option.CoffeeMilkRatio"

PROGRAM_OPTIONS = {
    bsh_key_to_translation_key(key): {
        ATTR_BSH_KEY: key,
        ATTR_SCHEMA: value,
    }
    for key, value in {
        "ConsumerProducts.CoffeeMaker.Option.FillQuantity": int,
        "ConsumerProducts.CoffeeMaker.Option.MultipleBeverages": bool,
        OPTION_COFFEE_MILK_RATIO: int,
        "Dishcare.Dishwasher.Option.IntensivZone": bool,
        "Dishcare.Dishwasher.Option.BrillianceDry": bool,
        "Dishcare.Dishwasher.Option.VarioSpeedPlus": bool,
        "Dishcare.Dishwasher.Option.SilenceOnDemand": bool,
        "Dishcare.Dishwasher.Option.HalfLoad": bool,
        "Dishcare.Dishwasher.Option.ExtraDry": bool,
        "Dishcare.Dishwasher.Option.HygienePlus": bool,
        "Dishcare.Dishwasher.Option.EcoDry": bool,
        "Dishcare.Dishwasher.Option.ZeoliteDry": bool,
        "Cooking.Oven.Option.SetpointTemperature": int,
        "Cooking.Oven.Option.FastPreHeat": bool,
        "LaundryCare.Washer.Option.IDos1Active": bool,
        "LaundryCare.Washer.Option.IDos2Active": bool,
    }.items()
}

TIME_PROGRAM_OPTIONS = {
    bsh_key_to_translation_key(key): {
        ATTR_BSH_KEY: key,
        ATTR_SCHEMA: value,
    }
    for key, value in {
        "BSH.Common.Option.StartInRelative": cv.time_period_str,
        BSH_COMMON_OPTION_DURATION: cv.time_period_str,
        "BSH.Common.Option.FinishInRelative": cv.time_period_str,
    }.items()
}


SERVICE_SETTING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
    }
)

SERVICE_OPTIONS_SCHEMA = (
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): str,
            vol.Optional(ATTR_CUSTOM_OPTIONS): vol.All(
                [
                    vol.Schema(
                        {
                            vol.Required(ATTR_KEY): str,
                            vol.Required(ATTR_VALUE): vol.Any(int, str, bool),
                            vol.Optional(ATTR_UNIT): str,
                        }
                    )
                ]
            ),
        }
    )
    .extend(
        {
            vol.Optional(key): vol.In(
                cast(dict[str, str], value[ATTR_ALLOWED_VALUES]).keys()
            )
            for key, value in PROGRAM_ENUM_OPTIONS.items()
        }
    )
    .extend(
        {
            vol.Optional(key): value[ATTR_SCHEMA]
            for key, value in cast(
                dict[str, dict[str, Any]], PROGRAM_OPTIONS | TIME_PROGRAM_OPTIONS
            ).items()
        }
    )
)

SERVICE_SET_OPTION_SCHEMA = vol.Any(
    {  # DEPRECATED: Remove in 2025.6.0
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, bool),
        vol.Optional(ATTR_UNIT): str,
    },
    {
        **SERVICE_OPTIONS_SCHEMA.schema,
    },
)

SERVICE_PROGRAM_SCHEMA = vol.Any(
    {  # DEPRECATED: Remove in 2025.6.0
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required(ATTR_PROGRAM): str,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(int, str),
        vol.Optional(ATTR_UNIT): str,
    },
    {
        vol.Required(ATTR_PROGRAM): str,
        vol.Optional(ATTR_START): bool,
        **SERVICE_OPTIONS_SCHEMA.schema,
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


def _get_appliance_or_raise_service_validation_error(
    hass: HomeAssistant, device_id: str
) -> api.HomeConnectAppliance:
    """Return a Home Connect appliance instance or raise a service validation error."""
    try:
        return _get_appliance(hass, device_id)
    except (ValueError, AssertionError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="appliance_not_found",
            translation_placeholders={
                "device_id": device_id,
            },
        ) from err


async def _run_appliance_service[*_Ts](
    hass: HomeAssistant,
    appliance: api.HomeConnectAppliance,
    method: str,
    *args: *_Ts,
    error_translation_key: str,
    error_translation_placeholders: dict[str, str] | None = None,
) -> None:
    try:
        await hass.async_add_executor_job(getattr(appliance, method), *args)
    except api.HomeConnectError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=error_translation_key,
            translation_placeholders={
                **get_dict_from_home_connect_error(err),
                **(error_translation_placeholders or {}),
            },
        ) from err


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: C901
    """Set up Home Connect component."""

    async def _async_service_program(call: ServiceCall, method: str) -> None:
        """Execute calls to services taking a program."""
        data = dict(call.data)
        program = data.pop(ATTR_PROGRAM)
        if program in TRANSLATION_KEYS_PROGRAMS_MAP:
            program = TRANSLATION_KEYS_PROGRAMS_MAP[program]
        device_id = data.pop(ATTR_DEVICE_ID)

        await _run_appliance_service(
            hass,
            _get_appliance_or_raise_service_validation_error(hass, device_id),
            method,
            program,
            get_options(data),
            error_translation_key=method,
            error_translation_placeholders={
                SVE_TRANSLATION_PLACEHOLDER_PROGRAM: program,
            },
        )

    def get_options(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a dict with the options ready to be sent to Home Connect API."""
        options: list[dict[str, Any]] = []

        custom_options: list[dict[str, Any]] = data.pop(ATTR_CUSTOM_OPTIONS, None)
        if custom_options is not None:
            options.extend(custom_options)

        if ATTR_KEY in data and ATTR_VALUE in data:
            async_create_issue(
                hass,
                DOMAIN,
                "moved_program_options_keys",
                breaks_in_ha_version="2025.6.0",
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="moved_program_options_keys",
                translation_placeholders={
                    "old_action": "\n".join(
                        [
                            "```yaml",
                            f"action: {DOMAIN}.{SERVICE_SELECT_PROGRAM}",
                            "data:",
                            f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                            f'  {ATTR_PROGRAM}: "Dishcare.Dishwasher.Program.Auto2"',
                            f'  {ATTR_KEY}: "BSH.Common.Option.StartInRelative"',
                            f'  {ATTR_VALUE}: "1800"',
                            f'  {ATTR_UNIT}: "seconds"',
                            "```",
                        ]
                    ),
                    "action_options": "\n  ".join(
                        [
                            "```yaml",
                            f"action: {DOMAIN}.{SERVICE_SELECT_PROGRAM}",
                            "data:",
                            f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                            f'  {ATTR_PROGRAM}: "Dishcare.Dishwasher.Program.Auto2"',
                            f"  {bsh_key_to_translation_key("BSH.Common.Option.StartInRelative")}: 1800",
                            "```",
                        ]
                    ),
                    "action_custom_options": "\n  ".join(
                        [
                            "```yaml",
                            f"action: {DOMAIN}.{SERVICE_SELECT_PROGRAM}",
                            "data:",
                            f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                            f'  {ATTR_PROGRAM}: "Dishcare.Dishwasher.Program.Auto2"',
                            f"  {ATTR_CUSTOM_OPTIONS}:",
                            f'    - {ATTR_KEY}: "BSH.Common.Option.StartInRelative"',
                            f"      {ATTR_VALUE}: 1800",
                            f'      {ATTR_UNIT}: "seconds"',
                            "```",
                        ]
                    ),
                },
            )
            if ATTR_UNIT in data:
                options.append(
                    {
                        ATTR_KEY: data.pop(ATTR_KEY),
                        ATTR_VALUE: data.pop(ATTR_VALUE),
                        ATTR_UNIT: data.pop(ATTR_UNIT),
                    }
                )
            else:
                options.append(
                    {ATTR_KEY: data.pop(ATTR_KEY), ATTR_VALUE: data.pop(ATTR_VALUE)}
                )

        for option, value in data.items():
            if option in PROGRAM_ENUM_OPTIONS:
                bsh_option_key = PROGRAM_ENUM_OPTIONS[option][ATTR_BSH_KEY]
                bsh_value_key = PROGRAM_ENUM_OPTIONS[option][ATTR_ALLOWED_VALUES][value]
                options.append({ATTR_KEY: bsh_option_key, ATTR_VALUE: bsh_value_key})
            elif option in PROGRAM_OPTIONS:
                bsh_key = PROGRAM_OPTIONS[option][ATTR_BSH_KEY]
                if bsh_key == OPTION_COFFEE_MILK_RATIO:
                    value = f"ConsumerProducts.CoffeeMaker.EnumType.CoffeeMilkRatio.{int(value)}Percent"
                options.append({ATTR_KEY: bsh_key, ATTR_VALUE: value})
            elif option in TIME_PROGRAM_OPTIONS:
                bsh_key = TIME_PROGRAM_OPTIONS[option][ATTR_BSH_KEY]
                value = int(cast(timedelta, value).total_seconds())
                options.append({ATTR_KEY: bsh_key, ATTR_VALUE: value})
        return options

    async def _async_service_command(call: ServiceCall, command: str) -> None:
        """Execute calls to services executing a command."""
        device_id = call.data[ATTR_DEVICE_ID]

        await _run_appliance_service(
            hass,
            _get_appliance_or_raise_service_validation_error(hass, device_id),
            "execute_command",
            command,
            error_translation_key="execute_command",
            error_translation_placeholders={
                "command": command,
            },
        )

    async def async_service_set_program_options(call: ServiceCall, method: str) -> None:
        """Execute calls to services setting program options."""
        data = dict(call.data)
        device_id = data.pop(ATTR_DEVICE_ID)

        await _run_appliance_service(
            hass,
            _get_appliance_or_raise_service_validation_error(hass, device_id),
            "put",
            f"/programs/{method}/options",
            {"data": {"options": get_options(data)}},
            error_translation_key="set_program_options",
        )

    async def async_service_option_active(call: ServiceCall) -> None:
        """Service for setting an option for an active program."""
        await async_service_set_program_options(call, "active")

    async def async_service_option_selected(call: ServiceCall) -> None:
        """Service for setting an option for a selected program."""
        await async_service_set_program_options(call, "selected")

    async def async_service_setting(call: ServiceCall) -> None:
        """Service for changing a setting."""
        key = call.data[ATTR_KEY]
        value = call.data[ATTR_VALUE]
        device_id = call.data[ATTR_DEVICE_ID]

        appliance = _get_appliance_or_raise_service_validation_error(hass, device_id)
        await _run_appliance_service(
            hass,
            appliance,
            "set_setting",
            key,
            value,
            error_translation_key="set_setting",
            error_translation_placeholders={
                SVE_TRANSLATION_PLACEHOLDER_KEY: key,
                SVE_TRANSLATION_PLACEHOLDER_VALUE: value,
                SVE_TRANSLATION_PLACEHOLDER_ENTITY_ID: appliance.name,
            },
        )

    async def async_service_pause_program(call: ServiceCall) -> None:
        """Service for pausing a program."""
        await _async_service_command(call, BSH_PAUSE)

    async def async_service_resume_program(call: ServiceCall) -> None:
        """Service for resuming a paused program."""
        await _async_service_command(call, BSH_RESUME)

    async def async_service_select_program(call: ServiceCall) -> None:
        """Service for selecting a program."""
        await _async_service_program(call, "select_program")

    async def async_service_start_program(call: ServiceCall) -> None:
        """Service for starting a program."""
        await _async_service_program(call, "start_program")

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPTION_ACTIVE,
        async_service_option_active,
        schema=SERVICE_SET_OPTION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_OPTION_SELECTED,
        async_service_option_selected,
        schema=SERVICE_SET_OPTION_SCHEMA,
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
