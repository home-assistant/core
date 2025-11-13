"""Support for services."""

from typing import TYPE_CHECKING

from aioshelly.const import RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import voluptuous as vol

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

from .const import DOMAIN
from .coordinator import ShellyConfigEntry
from .utils import get_device_entry_gen

ATTR_KEY = "key"

SERVICE_KVS_GET = "kvs_get"
SERVICE_KVS_GET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_KEY): str,
    }
)


async def async_kvs_get(call: ServiceCall) -> ServiceResponse:
    """Handle the kvs_get service call."""
    key = call.data[ATTR_KEY]
    device_id = call.data["device_id"]

    device_registry = dr.async_get(call.hass)
    device = device_registry.async_get(device_id)

    if TYPE_CHECKING:
        assert device is not None

    # Find the config entry for this device
    config_entry: ShellyConfigEntry | None = None
    for entry_id in device.config_entries:
        entry = call.hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            config_entry = entry
            break

    if TYPE_CHECKING:
        assert config_entry is not None

    # Check if device is RPC (Gen2+) device
    if get_device_entry_gen(config_entry) not in RPC_GENERATIONS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_rpc_device",
        )

    runtime_data = config_entry.runtime_data

    if not runtime_data.rpc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_ready",
        )

    try:
        response = await runtime_data.rpc.device.call_rpc("KVS.Get", {"key": key})
    except RpcCallError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="rpc_call_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except DeviceConnectionError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_connection_error",
        ) from err
    else:
        result: dict[str, JsonValueType] = {}
        result["value"] = response.get("value")

        return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for Shelly integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_KVS_GET,
        async_kvs_get,
        schema=SERVICE_KVS_GET_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
