"""Implement Enphase Envoy services."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import orjson
from pyenphase import Envoy, EnvoyError
from pyenphase.exceptions import EnvoyHTTPStatusError
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator

ATTR_ENVOY = "envoy"
ATTR_ENDPOINT = "endpoint"
ATTR_JSON_DATA = "data"
ATTR_METHOD = "method"

SERVICE_GET_FIRMWARE = "get_firmware"
SERVICE_GET_FIRMWARE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENVOY): cv.entity_id,
    },
)
SERVICE_GET_LAST_DATA = "get_last_data"
SERVICE_GET_LAST_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENVOY): cv.entity_id,
        vol.Optional(ATTR_ENDPOINT): cv.string,
    }
)
SERVICE_GET_CURRENT_DATA = "get_current_data"
SERVICE_GET_CURRENT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENVOY): cv.entity_id,
        vol.Required(ATTR_ENDPOINT): cv.string,
    }
)
SERVICE_POST_DATA = "post_data"
SERVICE_POST_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENVOY): cv.entity_id,
        vol.Required(ATTR_ENDPOINT): cv.string,
        vol.Required(ATTR_JSON_DATA): cv.string,
        vol.Optional(ATTR_METHOD): cv.string,
    }
)

SERVICE_LIST: list[str] = [
    SERVICE_GET_LAST_DATA,
    SERVICE_GET_CURRENT_DATA,
    SERVICE_POST_DATA,
    SERVICE_GET_FIRMWARE,
]

_LOGGER = logging.getLogger(__name__)


# keep track of registered envoys
envoylist: dict[str, EnphaseUpdateCoordinator] = {}


def _find_envoy_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> EnphaseUpdateCoordinator:
    """Find envoy serialnumber from service data and return envoy coordinator.

    The servicecall parameter ATTR_ENVOY should contain an entity_id
    of an entity associated with the target Envoy. Alternatively the envoy
    serial number can be passed in the format envoy.serialnumber.
    """
    identifier = str(call.data.get(ATTR_ENVOY))
    # try if envoy.serial format was passed
    some_parts = identifier.split(".")
    if len(some_parts) > 1 and (coordinator := envoylist.get(str(some_parts[1]))):
        return coordinator
    # from here assume an entity id was passed
    entity_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    # find serial number from device from entity
    if (
        (entry := entity_reg.async_get(identifier))
        and entry.device_id
        and (entry_dev := dev_reg.async_get(entry.device_id))
    ):
        # see if this is the envoy
        if entry_dev.serial_number and (
            coordinator := envoylist.get(entry_dev.serial_number)
        ):
            return coordinator
        # try if some child device entity was passed
        if (
            entry_dev.via_device_id
            and (via_device := dev_reg.async_get(entry_dev.via_device_id))
            and via_device.serial_number
            and (coordinator := envoylist.get(via_device.serial_number))
        ):
            return coordinator
    # too bad, nothing we recognize
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="envoy_service_envoy_not_found",
        translation_placeholders={
            "service": call.service,
            "args": identifier,
        },
    )


def _get_sub_dict_list(dict_or_list: Any, path: str) -> Any:
    """Extract nested dict/list values using comma separated list of keys and/or index values.

    Returns sub dict or sub list from passed dict or list using specified keys
    and/or list indexes from a commas separated string. Any numeric dict keys must
    be surrounded by ' or "
    """
    filter_path: str = ""
    for key_or_index in path.split(","):
        # if numeric use as list index, unless wrapped in quotes
        use_key_or_index = (
            int(key_or_index)
            if (isnumber := key_or_index.isnumeric())
            else key_or_index.replace("'", "").replace('"', "")
        )
        filter_path = filter_path if isnumber else f"{key_or_index}"
        dict_or_list = dict_or_list[use_key_or_index]
    return dict_or_list, filter_path


async def _get_envoy_reply(
    coordinator: EnphaseUpdateCoordinator,
    endpoint: str,
    call: ServiceCall,
    data: dict[str, Any] | None = None,
    method: str | None = None,
) -> dict[str, Any]:
    """Send request to Envoy and return reply content as string.

    Send GET, POST or PUT request to Envoy and return data reply.
    If no data is specified a GET request will be send.
    If data is specified and a method, the method is used.
    If data and no method a POST is used.
    """
    envoy: Envoy = coordinator.envoy
    if not envoy.data:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="not_initialized",
            translation_placeholders={"service": call.service},
        )
    endpoint_filter = endpoint.split(",")
    try:
        reply: httpx.Response = await envoy.request(endpoint_filter[0], data=data)
    except (
        EnvoyError,
        httpx.RequestError,
        httpx.HTTPStatusError,
    ) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="envoy_error",
            translation_placeholders={"host": envoy.host, "args": err.args[0]},
        ) from err
    if reply.status_code >= 300:
        raise EnvoyHTTPStatusError(reply.status_code, endpoint_filter[0])
    try:
        result = orjson.loads(reply.content)
    except orjson.JSONDecodeError:
        # it's xml or html
        result = f"{reply.content.decode('utf-8')}"
    if len(endpoint_filter) == 1:
        return {endpoint: result}
    # if endpoint_filter extract specified dict keys/list indexes
    try:
        result = _get_sub_dict_list({endpoint_filter[0]: result}, endpoint)
    except (KeyError, IndexError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="envoy_service_invalid_parameter",
            translation_placeholders={
                "service": call.service,
                "args": err.args[0],
            },
        ) from err

    return {result[1]: result[0]}


async def setup_hass_services(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> ServiceResponse:
    """Configure Home Assistant services for Enphase_Envoy."""

    # keep track of all envoy
    entry_envoy: Envoy = entry.runtime_data.envoy
    if entry_envoy.serial_number:
        envoylist[entry_envoy.serial_number] = entry.runtime_data

    # if services are already registered by another envoy don't define again
    if hass.services.async_services_for_domain(DOMAIN):
        return None

    async def get_raw_json(call: ServiceCall) -> Any:
        """Return data from envoy.data.raw cache as json."""
        coordinator: EnphaseUpdateCoordinator = _find_envoy_coordinator(hass, call)
        envoy_to_use: Envoy = coordinator.envoy
        if not envoy_to_use.data or not envoy_to_use.data.raw:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_initialized",
                translation_placeholders={"service": call.service},
            )
        endpoint = call.data.get(ATTR_ENDPOINT)
        # if no endpoint or just raw endpoint return all raw data
        if not endpoint or endpoint == "raw":
            return {"raw": envoy_to_use.data.raw}

        # endpoint is comma separated list, make sure first one is raw
        endpoint = endpoint if endpoint.split(",")[0] == "raw" else f"raw,{endpoint}"
        # extract specified dict keys/list indexes from raw data
        try:
            result = _get_sub_dict_list({"raw": envoy_to_use.data.raw}, endpoint)
        except (KeyError, IndexError, TypeError) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_invalid_parameter",
                translation_placeholders={
                    "service": call.service,
                    "args": err.args[0],
                },
            ) from err
        # return result with last filter key as dict key
        return {result[1]: result[0]}

    async def get_json_reply(call: ServiceCall) -> Any:
        """Send get request to Envoy and return reply."""
        coordinator: EnphaseUpdateCoordinator = _find_envoy_coordinator(hass, call)
        endpoint: str = call.data[ATTR_ENDPOINT]
        try:
            return await _get_envoy_reply(coordinator, endpoint, call=call)
        except (KeyError, IndexError, TypeError) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_invalid_parameter",
                translation_placeholders={
                    "service": call.service,
                    "args": err.args[0],
                },
            ) from err
        except (EnvoyError,) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_error",
                translation_placeholders={
                    "service": call.service,
                    "args": err.args[0],
                },
            ) from err

    async def post_json(call: ServiceCall) -> ServiceResponse:
        """Send POST or PUT request to Envoy and return reply."""
        coordinator: EnphaseUpdateCoordinator = _find_envoy_coordinator(hass, call)
        endpoint: str = call.data[ATTR_ENDPOINT]
        data = call.data[ATTR_JSON_DATA]
        # Make sure we have proper json string
        try:
            json_data = orjson.loads(data)
        except orjson.JSONDecodeError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_invalid_parameter",
                translation_placeholders={
                    "service": call.service,
                    "args": err.args[0],
                },
            ) from err
        # data comes from user defined action or script
        # make sure we have a dict as that's only thing we can send.
        if not isinstance(json_data, dict):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_invalid_parameter",
                translation_placeholders={
                    "service": call.service,
                    "args": f"No Dict: '{data}'",
                },
            )
        method = call.data.get(ATTR_METHOD)
        try:
            response = await _get_envoy_reply(
                coordinator,
                endpoint,
                call=call,
                data=json_data,
                method=method,
            )
        except (EnvoyError, EnvoyHTTPStatusError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_error",
                translation_placeholders={
                    "service": call.service,
                    "args": err.args[0],
                },
            ) from err
        # tell coordinator to refresh data
        await coordinator.async_request_refresh()
        return response

    async def get_firmware(call: ServiceCall) -> ServiceResponse:
        """Read firmware version from Envoy using GET request."""
        coordinator: EnphaseUpdateCoordinator = _find_envoy_coordinator(hass, call)
        # coordintaor only gets firmware at config load
        envoy_to_use: Envoy = coordinator.envoy
        # coordinator only gets firmware at config load
        previous_firmware: str = envoy_to_use.firmware
        # envoy setup only reads firmware from envoy, use it
        try:
            await envoy_to_use.setup()
        except EnvoyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_error",
                translation_placeholders={
                    "service": call.service,
                    "args": err.args[0],
                },
            ) from err
        # if there's difference between coordinator fw
        # and envoy one, user should reload the entry
        return {
            "firmware": envoy_to_use.firmware,
            "previous_firmware": previous_firmware,
        }

    # declare services
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LAST_DATA,
        get_raw_json,
        schema=SERVICE_GET_LAST_DATA_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CURRENT_DATA,
        get_json_reply,
        schema=SERVICE_GET_CURRENT_DATA_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_POST_DATA,
        post_json,
        schema=SERVICE_POST_DATA_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_FIRMWARE,
        get_firmware,
        schema=SERVICE_GET_FIRMWARE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return None


async def unload_hass_services(hass: HomeAssistant, envoy: Envoy) -> None:
    """Unload services for Enphase Envoy integration."""

    if envoy.serial_number:
        envoylist.pop(envoy.serial_number)
    # if there's still another envoy active don't remove services
    if envoylist:
        return
    for service in SERVICE_LIST:
        hass.services.async_remove(DOMAIN, service)
