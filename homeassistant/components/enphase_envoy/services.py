"""Implement Enphase Envoy service actions."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import orjson
from pyenphase import Envoy, EnvoyError
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator


def _normalize_endpoint(endpoint: str) -> str:
    """Ensure the endpoint starts with a leading slash."""
    if endpoint.startswith("/"):
        return endpoint
    return f"/{endpoint}"


ATTR_ENDPOINT = "endpoint"
ATTR_ENVOY_DEVICE_ID = "device_id"

ACTION_INSPECT = "inspect"
ACTION_INSPECT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENDPOINT): vol.All(cv.string, _normalize_endpoint),
        vol.Optional(ATTR_ENVOY_DEVICE_ID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


# keep track of loaded envoy entries to route service action calls
# to the correct coordinator when multiple envoys are present.
envoy_coordinators_list: dict[str, EnphaseUpdateCoordinator] = {}


def _find_envoy_coordinator(
    hass: HomeAssistant, device_id: str | None
) -> EnphaseUpdateCoordinator | None:
    """Find envoy coordinator.

    Returns coordinator for specified device_id. If device has
    parent, parent device will be used to find coordinator. If no
    device_id is specified, the first coordinator in the list is returned.
    """
    dev_reg = dr.async_get(hass)
    # find the device coordinator
    if device_id and (device_entry := dev_reg.async_get(device_id)):
        if device_entry.serial_number and (
            coordinator := envoy_coordinators_list.get(device_entry.serial_number)
        ):
            return coordinator
        # if child device was passed, use parent
        if (
            device_entry.via_device_id
            and (via_device := dev_reg.async_get(device_entry.via_device_id))
            and via_device.serial_number
            and (coordinator := envoy_coordinators_list.get(via_device.serial_number))
        ):
            return coordinator
    # use first entry if no specific id was specified
    if device_id is None and len(envoy_coordinators_list) > 0:
        return next(iter(envoy_coordinators_list.values()))

    return None


async def add_envoy_to_coordinators_list(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> None:
    """Add Envoy config entry to list of known envoy coordinators."""
    # keep track of our coordinator
    if (entry_envoy := entry.runtime_data.envoy) and entry_envoy.serial_number:
        envoy_coordinators_list[entry_envoy.serial_number] = entry.runtime_data


async def remove_envoy_from_coordinators_list(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> None:
    """Remove Envoy config entry from list of known envoy coordinators."""
    if (entry_envoy := entry.runtime_data.envoy) and entry_envoy.serial_number:
        envoy_coordinators_list.pop(entry_envoy.serial_number, None)


@callback
def setup_envoy_service_actions(hass: HomeAssistant) -> ServiceResponse:
    """Configure Home Assistant services for Enphase_Envoy."""

    async def inspect_action(call: ServiceCall) -> Any:
        """Inspect action sends get request to Envoy and returns reply."""
        device_id = call.data.get(ATTR_ENVOY_DEVICE_ID)
        if not (coordinator := _find_envoy_coordinator(hass, device_id)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="envoy_service_envoy_not_found",
                translation_placeholders={
                    "service": call.service,
                    "device_id": str(device_id),
                },
            )

        envoy: Envoy = coordinator.envoy
        if not envoy.data:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="not_initialized",
                translation_placeholders={"service": call.service},
            )
        endpoint: str = call.data[ATTR_ENDPOINT]
        _LOGGER.debug(
            "Service action %s for Envoy %s endpoint %s executing",
            call.service,
            envoy.serial_number,
            endpoint,
        )
        try:
            response: aiohttp.ClientResponse = await envoy.request(endpoint)
        except EnvoyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="envoy_error",
                translation_placeholders={"host": envoy.host, "args": err.args[0]},
            ) from err
        if response.status >= 300:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="envoy_error",
                translation_placeholders={
                    "host": envoy.host,
                    "args": f" Status:{response.status} - {response.reason}",
                },
            )
        try:
            result_data = await response.text()
            result = orjson.loads(result_data)
        except orjson.JSONDecodeError:
            # Try xml or html
            result = f"{result_data}"
        return {endpoint: result}

    # declare service actions
    hass.services.async_register(
        DOMAIN,
        ACTION_INSPECT,
        inspect_action,
        schema=ACTION_INSPECT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return None
