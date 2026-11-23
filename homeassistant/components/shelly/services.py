"""Support for services."""

import posixpath
from typing import Any, cast

from aiohttp import ClientResponseError
from aioshelly.const import RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import probatio

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN, CoverEntityFeature
from homeassistant.const import CommonServiceArgument
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import (
    async_get_device_and_config_entry,
    async_register_admin_service,
    async_register_platform_entity_service,
)
from homeassistant.helpers.typing import VolDictType
from homeassistant.util.json import JsonValueType

from .const import (
    CONF_SLEEP_PERIOD,
    DOMAIN,
    LOGGER,
    ShellyService,
    ShellyServiceArgument,
)
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .utils import get_device_entry_gen

# Commands that perform a factory reset or make the device unreachable
BLOCKED_RPC_METHODS = frozenset({"shelly.factoryreset", "shelly.resetwificonfig"})
BLOCKED_BLOCK_PARAMS = {"settings": "reset"}

SERVICE_COMMAND_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(ShellyServiceArgument.COMMAND): cv.string,
        probatio.Optional(ShellyServiceArgument.PARAMS): dict,
    }
)
SERVICE_GET_KVS_VALUE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(ShellyServiceArgument.KEY): str,
    }
)
SERVICE_SET_KVS_VALUE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Required(ShellyServiceArgument.KEY): str,
        probatio.Required(ShellyServiceArgument.VALUE): probatio.Any(
            str, int, float, bool, dict, list, None
        ),
    }
)
SERVICE_SET_COVER_POSITION_AND_TILT_SCHEMA: VolDictType = {
    probatio.Required(ShellyServiceArgument.POSITION): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=100)
    ),
    probatio.Required(ShellyServiceArgument.TILT_POSITION): probatio.All(
        probatio.Coerce(int), probatio.Range(min=0, max=100)
    ),
}


@callback
def async_get_config_entry_for_service_call(
    call: ServiceCall,
) -> ShellyConfigEntry:
    """Get the config entry related to a service call (by device ID)."""
    config_entry: ShellyConfigEntry
    _, config_entry = async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )

    if (
        config_entry.data.get(CONF_SLEEP_PERIOD, 0) > 0
        or get_device_entry_gen(config_entry) not in RPC_GENERATIONS
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="kvs_not_supported",
            translation_placeholders={"device": config_entry.title},
        )

    return config_entry


async def _async_execute_action(
    call: ServiceCall, method: str, args: tuple
) -> dict[str, Any]:
    """Execute action on the device."""
    config_entry = async_get_config_entry_for_service_call(call)

    runtime_data = config_entry.runtime_data

    if not runtime_data.rpc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_initialized",
            translation_placeholders={"device": config_entry.title},
        )

    action_method = getattr(runtime_data.rpc.device, method)

    try:
        response = await action_method(*args)
    except RpcCallError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="rpc_call_error",
            translation_placeholders={"device": config_entry.title},
        ) from err
    except DeviceConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_communication_error",
            translation_placeholders={"device": config_entry.title},
        ) from err
    else:
        return cast(dict[str, Any], response)


async def async_command(call: ServiceCall) -> ServiceResponse:
    """Handle the command service call."""
    config_entry: ShellyConfigEntry
    _, config_entry = async_get_device_and_config_entry(
        call.hass, DOMAIN, call.data[CommonServiceArgument.DEVICE_ID]
    )
    command: str = call.data[ShellyServiceArgument.COMMAND]
    params: dict[str, Any] | None = call.data.get(ShellyServiceArgument.PARAMS)
    placeholders = {"device": config_entry.title}

    if config_entry.data.get(CONF_SLEEP_PERIOD, 0) > 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="command_sleeping_device",
            translation_placeholders=placeholders,
        )

    runtime_data = config_entry.runtime_data
    is_rpc = get_device_entry_gen(config_entry) in RPC_GENERATIONS
    coordinator = runtime_data.rpc if is_rpc else runtime_data.block

    if not coordinator:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_initialized",
            translation_placeholders=placeholders,
        )

    if is_rpc:
        blocked = command.casefold() in BLOCKED_RPC_METHODS
    else:
        # The HTTP client resolves dot segments, so match what the device receives
        command = posixpath.normpath(f"/{command.strip('/')}").lstrip("/")
        blocked = BLOCKED_BLOCK_PARAMS.get(command.casefold()) in (params or {})
        if params is not None:
            if not all(isinstance(v, (str, int, float)) for v in params.values()):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="command_invalid_params",
                    translation_placeholders=placeholders,
                )
            # The HTTP client does not accept boolean query values
            params = {
                key: str(value).lower() if isinstance(value, bool) else value
                for key, value in params.items()
            }

    if blocked:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="command_not_allowed",
            translation_placeholders={**placeholders, "command": command},
        )

    # An RPC call on a closed connection raises RuntimeError
    if (
        isinstance(coordinator, ShellyRpcCoordinator)
        and not coordinator.device.connected
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_communication_error",
            translation_placeholders=placeholders,
        )

    LOGGER.debug(
        "Sending command %s to %s, params: %s", command, config_entry.title, params
    )

    try:
        if isinstance(coordinator, ShellyRpcCoordinator):
            response = await coordinator.device.call_rpc(command, params)
        else:
            response = await coordinator.device.http_request("get", command, params)
    except RpcCallError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rpc_error",
            translation_placeholders={
                **placeholders,
                "command": command,
                "code": str(err.code),
                "message": err.message,
            },
        ) from err
    except DeviceConnectionError as err:
        # Block devices reject an unknown endpoint or parameter with an HTTP status
        if isinstance(err.__cause__, ClientResponseError):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_http_error",
                translation_placeholders={
                    **placeholders,
                    "command": command,
                    "status": str(err.__cause__.status),
                },
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_communication_error",
            translation_placeholders=placeholders,
        ) from err
    except InvalidAuthError as err:
        await coordinator.async_shutdown_device_and_start_reauth()
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="auth_error",
            translation_placeholders=placeholders,
        ) from err

    LOGGER.debug(
        "Command %s response from %s: %s", command, config_entry.title, response
    )

    return cast(ServiceResponse, response or {})


async def async_get_kvs_value(call: ServiceCall) -> ServiceResponse:
    """Handle the get_kvs_value service call."""
    key = call.data[ShellyServiceArgument.KEY]

    response = await _async_execute_action(call, "kvs_get", (key,))

    result: dict[str, JsonValueType] = {}
    result["value"] = response["value"]

    return result


async def async_set_kvs_value(call: ServiceCall) -> None:
    """Handle the set_kvs_value service call."""
    await _async_execute_action(
        call,
        "kvs_set",
        (
            call.data[ShellyServiceArgument.KEY],
            call.data[ShellyServiceArgument.VALUE],
        ),
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for Shelly integration."""
    for service, method, schema, response in (
        (
            ShellyService.GET_KVS_VALUE,
            async_get_kvs_value,
            SERVICE_GET_KVS_VALUE_SCHEMA,
            SupportsResponse.ONLY,
        ),
        (
            ShellyService.SET_KVS_VALUE,
            async_set_kvs_value,
            SERVICE_SET_KVS_VALUE_SCHEMA,
            SupportsResponse.NONE,
        ),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            method,
            schema=schema,
            supports_response=response,
        )

    async_register_admin_service(
        hass,
        DOMAIN,
        ShellyService.COMMAND,
        async_command,
        schema=SERVICE_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        ShellyService.SET_COVER_POSITION_AND_TILT,
        entity_domain=COVER_DOMAIN,
        schema=SERVICE_SET_COVER_POSITION_AND_TILT_SCHEMA,
        func="async_set_cover_position_and_tilt",
        required_features=[
            CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION
        ],
    )
