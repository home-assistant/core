"""Support for services."""

from typing import TYPE_CHECKING, Any, cast

from aioshelly.const import RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util.json import JsonValueType

from .const import ATTR_KEY, ATTR_VALUE, CONF_SLEEP_PERIOD, DOMAIN
from .coordinator import ShellyConfigEntry
from .utils import get_device_entry_gen

SERVICE_GET_KVS_VALUE = "get_kvs_value"
SERVICE_SET_KVS_VALUE = "set_kvs_value"
SERVICE_GET_KVS_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_KEY): str,
    }
)
SERVICE_SET_KVS_VALUE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_KEY): str,
        vol.Required(ATTR_VALUE): vol.Any(str, int, float, bool, dict, list, None),
    }
)


@callback
def async_get_config_entry_for_service_call(
    call: ServiceCall,
) -> ShellyConfigEntry:
    """Get the config entry related to a service call (by device ID)."""
    device_registry = dr.async_get(call.hass)
    device_id = call.data[ATTR_DEVICE_ID]

    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    for entry_id in device_entry.config_entries:
        config_entry = call.hass.config_entries.async_get_entry(entry_id)

        if TYPE_CHECKING:
            assert config_entry

        if config_entry.domain != DOMAIN:
            continue
        if config_entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"device": config_entry.title},
            )
        if get_device_entry_gen(config_entry) not in RPC_GENERATIONS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="kvs_not_supported",
                translation_placeholders={"device": config_entry.title},
            )
        if config_entry.data.get(CONF_SLEEP_PERIOD, 0) > 0:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="kvs_not_supported",
                translation_placeholders={"device": config_entry.title},
            )
        return config_entry

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
        translation_placeholders={"device_id": device_id},
    )


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


async def async_get_kvs_value(call: ServiceCall) -> ServiceResponse:
    """Handle the get_kvs_value service call."""
    key = call.data[ATTR_KEY]

    response = await _async_execute_action(call, "kvs_get", (key,))

    result: dict[str, JsonValueType] = {}
    result[ATTR_VALUE] = response[ATTR_VALUE]

    return result


async def async_set_kvs_value(call: ServiceCall) -> None:
    """Handle the set_kvs_value service call."""
    await _async_execute_action(
        call, "kvs_set", (call.data[ATTR_KEY], call.data[ATTR_VALUE])
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for Shelly integration."""
    for service, method, schema, response in (
        (
            SERVICE_GET_KVS_VALUE,
            async_get_kvs_value,
            SERVICE_GET_KVS_VALUE_SCHEMA,
            SupportsResponse.ONLY,
        ),
        (
            SERVICE_SET_KVS_VALUE,
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
