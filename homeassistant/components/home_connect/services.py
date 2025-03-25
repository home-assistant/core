"""Custom actions (previously known as services) for the Home Connect integration."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, cast

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import (
    ArrayOfOptions,
    CommandKey,
    Option,
    OptionKey,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectError
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import (
    AFFECTS_TO_ACTIVE_PROGRAM,
    AFFECTS_TO_SELECTED_PROGRAM,
    ATTR_AFFECTS_TO,
    ATTR_KEY,
    ATTR_PROGRAM,
    ATTR_UNIT,
    ATTR_VALUE,
    DOMAIN,
    PROGRAM_ENUM_OPTIONS,
    SERVICE_OPTION_ACTIVE,
    SERVICE_OPTION_SELECTED,
    SERVICE_PAUSE_PROGRAM,
    SERVICE_RESUME_PROGRAM,
    SERVICE_SELECT_PROGRAM,
    SERVICE_SET_PROGRAM_AND_OPTIONS,
    SERVICE_SETTING,
    SERVICE_START_PROGRAM,
    TRANSLATION_KEYS_PROGRAMS_MAP,
)
from .coordinator import HomeConnectConfigEntry
from .utils import bsh_key_to_translation_key, get_dict_from_home_connect_error

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


PROGRAM_OPTIONS = {
    bsh_key_to_translation_key(key): (
        key,
        value,
    )
    for key, value in {
        OptionKey.BSH_COMMON_DURATION: int,
        OptionKey.BSH_COMMON_START_IN_RELATIVE: int,
        OptionKey.BSH_COMMON_FINISH_IN_RELATIVE: int,
        OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_FILL_QUANTITY: int,
        OptionKey.CONSUMER_PRODUCTS_COFFEE_MAKER_MULTIPLE_BEVERAGES: bool,
        OptionKey.DISHCARE_DISHWASHER_INTENSIV_ZONE: bool,
        OptionKey.DISHCARE_DISHWASHER_BRILLIANCE_DRY: bool,
        OptionKey.DISHCARE_DISHWASHER_VARIO_SPEED_PLUS: bool,
        OptionKey.DISHCARE_DISHWASHER_SILENCE_ON_DEMAND: bool,
        OptionKey.DISHCARE_DISHWASHER_HALF_LOAD: bool,
        OptionKey.DISHCARE_DISHWASHER_EXTRA_DRY: bool,
        OptionKey.DISHCARE_DISHWASHER_HYGIENE_PLUS: bool,
        OptionKey.DISHCARE_DISHWASHER_ECO_DRY: bool,
        OptionKey.DISHCARE_DISHWASHER_ZEOLITE_DRY: bool,
        OptionKey.COOKING_OVEN_SETPOINT_TEMPERATURE: int,
        OptionKey.COOKING_OVEN_FAST_PRE_HEAT: bool,
        OptionKey.LAUNDRY_CARE_WASHER_I_DOS_1_ACTIVE: bool,
        OptionKey.LAUNDRY_CARE_WASHER_I_DOS_2_ACTIVE: bool,
    }.items()
}


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

# DEPRECATED: Remove in 2025.9.0
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

# DEPRECATED: Remove in 2025.9.0
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


def _require_program_or_at_least_one_option(data: dict) -> dict:
    if ATTR_PROGRAM not in data and not any(
        option_key in data for option_key in (PROGRAM_ENUM_OPTIONS | PROGRAM_OPTIONS)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="required_program_or_one_option_at_least",
        )
    return data


SERVICE_PROGRAM_AND_OPTIONS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_DEVICE_ID): str,
            vol.Required(ATTR_AFFECTS_TO): vol.In(
                [AFFECTS_TO_ACTIVE_PROGRAM, AFFECTS_TO_SELECTED_PROGRAM]
            ),
            vol.Optional(ATTR_PROGRAM): vol.In(TRANSLATION_KEYS_PROGRAMS_MAP.keys()),
        }
    )
    .extend(
        {
            vol.Optional(translation_key): vol.In(allowed_values.keys())
            for translation_key, (
                key,
                allowed_values,
            ) in PROGRAM_ENUM_OPTIONS.items()
        }
    )
    .extend(
        {
            vol.Optional(translation_key): schema
            for translation_key, (key, schema) in PROGRAM_OPTIONS.items()
        }
    ),
    _require_program_or_at_least_one_option,
)

SERVICE_COMMAND_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): str})


async def _get_client_and_ha_id(
    hass: HomeAssistant, device_id: str
) -> tuple[HomeConnectClient, str]:
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_entry_not_found",
            translation_placeholders={
                "device_id": device_id,
            },
        )
    entry: HomeConnectConfigEntry | None = None
    for entry_id in device_entry.config_entries:
        _entry = hass.config_entries.async_get_entry(entry_id)
        assert _entry
        if _entry.domain == DOMAIN:
            entry = cast(HomeConnectConfigEntry, _entry)
            break
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={
                "device_id": device_id,
            },
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


async def _async_service_program(call: ServiceCall, start: bool) -> None:
    """Execute calls to services taking a program."""
    program = call.data[ATTR_PROGRAM]
    client, ha_id = await _get_client_and_ha_id(call.hass, call.data[ATTR_DEVICE_ID])

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

    async_create_issue(
        call.hass,
        DOMAIN,
        "deprecated_set_program_and_option_actions",
        breaks_in_ha_version="2025.9.0",
        is_fixable=True,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_set_program_and_option_actions",
        translation_placeholders={
            "new_action_key": SERVICE_SET_PROGRAM_AND_OPTIONS,
            "remove_release": "2025.9.0",
            "deprecated_action_yaml": "\n".join(
                [
                    "```yaml",
                    f"action: {DOMAIN}.{SERVICE_START_PROGRAM if start else SERVICE_SELECT_PROGRAM}",
                    "data:",
                    f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                    f"  {ATTR_PROGRAM}: {program}",
                    *([f"  {ATTR_KEY}: {options[0].key}"] if options else []),
                    *([f"  {ATTR_VALUE}: {options[0].value}"] if options else []),
                    *(
                        [f"  {ATTR_UNIT}: {options[0].unit}"]
                        if options and options[0].unit
                        else []
                    ),
                    "```",
                ]
            ),
            "new_action_yaml": "\n  ".join(
                [
                    "```yaml",
                    f"action: {DOMAIN}.{SERVICE_SET_PROGRAM_AND_OPTIONS}",
                    "data:",
                    f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                    f"  {ATTR_AFFECTS_TO}: {AFFECTS_TO_ACTIVE_PROGRAM if start else AFFECTS_TO_SELECTED_PROGRAM}",
                    f"  {ATTR_PROGRAM}: {bsh_key_to_translation_key(program.value)}",
                    *(
                        [
                            f"  {bsh_key_to_translation_key(options[0].key)}: {options[0].value}"
                        ]
                        if options
                        else []
                    ),
                    "```",
                ]
            ),
            "repo_link": "[aiohomeconnect](https://github.com/MartinHjelmare/aiohomeconnect)",
        },
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
                "program": program,
            },
        ) from err


async def _async_service_set_program_options(call: ServiceCall, active: bool) -> None:
    """Execute calls to services taking a program."""
    option_key = call.data[ATTR_KEY]
    value = call.data[ATTR_VALUE]
    unit = call.data.get(ATTR_UNIT)
    client, ha_id = await _get_client_and_ha_id(call.hass, call.data[ATTR_DEVICE_ID])

    async_create_issue(
        call.hass,
        DOMAIN,
        "deprecated_set_program_and_option_actions",
        breaks_in_ha_version="2025.9.0",
        is_fixable=True,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_set_program_and_option_actions",
        translation_placeholders={
            "new_action_key": SERVICE_SET_PROGRAM_AND_OPTIONS,
            "remove_release": "2025.9.0",
            "deprecated_action_yaml": "\n".join(
                [
                    "```yaml",
                    f"action: {DOMAIN}.{SERVICE_OPTION_ACTIVE if active else SERVICE_OPTION_SELECTED}",
                    "data:",
                    f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                    f"  {ATTR_KEY}: {option_key}",
                    f"  {ATTR_VALUE}: {value}",
                    *([f"  {ATTR_UNIT}: {unit}"] if unit else []),
                    "```",
                ]
            ),
            "new_action_yaml": "\n  ".join(
                [
                    "```yaml",
                    f"action: {DOMAIN}.{SERVICE_SET_PROGRAM_AND_OPTIONS}",
                    "data:",
                    f"  {ATTR_DEVICE_ID}: DEVICE_ID",
                    f"  {ATTR_AFFECTS_TO}: {AFFECTS_TO_ACTIVE_PROGRAM if active else AFFECTS_TO_SELECTED_PROGRAM}",
                    f"  {bsh_key_to_translation_key(option_key)}: {value}",
                    "```",
                ]
            ),
            "repo_link": "[aiohomeconnect](https://github.com/MartinHjelmare/aiohomeconnect)",
        },
    )
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
                "key": option_key,
                "value": str(value),
            },
        ) from err


async def _async_service_command(call: ServiceCall, command_key: CommandKey) -> None:
    """Execute calls to services executing a command."""
    client, ha_id = await _get_client_and_ha_id(call.hass, call.data[ATTR_DEVICE_ID])

    async_create_issue(
        call.hass,
        DOMAIN,
        "deprecated_command_actions",
        breaks_in_ha_version="2025.9.0",
        is_fixable=True,
        is_persistent=True,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_command_actions",
    )

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


async def async_service_option_active(call: ServiceCall) -> None:
    """Service for setting an option for an active program."""
    await _async_service_set_program_options(call, True)


async def async_service_option_selected(call: ServiceCall) -> None:
    """Service for setting an option for a selected program."""
    await _async_service_set_program_options(call, False)


async def async_service_setting(call: ServiceCall) -> None:
    """Service for changing a setting."""
    key = call.data[ATTR_KEY]
    value = call.data[ATTR_VALUE]
    client, ha_id = await _get_client_and_ha_id(call.hass, call.data[ATTR_DEVICE_ID])

    try:
        await client.set_setting(ha_id, setting_key=key, value=value)
    except HomeConnectError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_setting",
            translation_placeholders={
                **get_dict_from_home_connect_error(err),
                "key": key,
                "value": str(value),
            },
        ) from err


async def async_service_pause_program(call: ServiceCall) -> None:
    """Service for pausing a program."""
    await _async_service_command(call, CommandKey.BSH_COMMON_PAUSE_PROGRAM)


async def async_service_resume_program(call: ServiceCall) -> None:
    """Service for resuming a paused program."""
    await _async_service_command(call, CommandKey.BSH_COMMON_RESUME_PROGRAM)


async def async_service_select_program(call: ServiceCall) -> None:
    """Service for selecting a program."""
    await _async_service_program(call, False)


async def async_service_set_program_and_options(call: ServiceCall) -> None:
    """Service for setting a program and options."""
    data = dict(call.data)
    program = data.pop(ATTR_PROGRAM, None)
    affects_to = data.pop(ATTR_AFFECTS_TO)
    client, ha_id = await _get_client_and_ha_id(call.hass, data.pop(ATTR_DEVICE_ID))

    options: list[Option] = []

    for option, value in data.items():
        if option in PROGRAM_ENUM_OPTIONS:
            options.append(
                Option(
                    PROGRAM_ENUM_OPTIONS[option][0],
                    PROGRAM_ENUM_OPTIONS[option][1][value],
                )
            )
        elif option in PROGRAM_OPTIONS:
            option_key = PROGRAM_OPTIONS[option][0]
            options.append(Option(option_key, value))

    method_call: Awaitable[Any]
    exception_translation_key: str
    if program:
        program = (
            program
            if isinstance(program, ProgramKey)
            else TRANSLATION_KEYS_PROGRAMS_MAP[program]
        )

        if affects_to == AFFECTS_TO_ACTIVE_PROGRAM:
            method_call = client.start_program(
                ha_id, program_key=program, options=options
            )
            exception_translation_key = "start_program"
        elif affects_to == AFFECTS_TO_SELECTED_PROGRAM:
            method_call = client.set_selected_program(
                ha_id, program_key=program, options=options
            )
            exception_translation_key = "select_program"
    else:
        array_of_options = ArrayOfOptions(options)
        if affects_to == AFFECTS_TO_ACTIVE_PROGRAM:
            method_call = client.set_active_program_options(
                ha_id, array_of_options=array_of_options
            )
            exception_translation_key = "set_options_active_program"
        else:
            # affects_to is AFFECTS_TO_SELECTED_PROGRAM
            method_call = client.set_selected_program_options(
                ha_id, array_of_options=array_of_options
            )
            exception_translation_key = "set_options_selected_program"

    try:
        await method_call
    except HomeConnectError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=exception_translation_key,
            translation_placeholders={
                **get_dict_from_home_connect_error(err),
                **({"program": program} if program else {}),
            },
        ) from err


async def async_service_start_program(call: ServiceCall) -> None:
    """Service for starting a program."""
    await _async_service_program(call, True)


def register_actions(hass: HomeAssistant) -> None:
    """Register custom actions."""

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PROGRAM_AND_OPTIONS,
        async_service_set_program_and_options,
        schema=SERVICE_PROGRAM_AND_OPTIONS_SCHEMA,
    )
