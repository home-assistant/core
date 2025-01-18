"""Implement Enphase Envoy services."""

from __future__ import annotations

import logging

from pyenphase import Envoy, EnvoyError
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

SERVICE_GET_FIRMWARE = "get_firmware"
SERVICE_GET_FIRMWARE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENVOY): cv.entity_id,
    },
)

SERVICE_LIST: list[str] = [
    SERVICE_GET_FIRMWARE,
]

_LOGGER = logging.getLogger(__name__)


# keep track of registered envoys
envoylist: dict[str, EnphaseUpdateCoordinator] = {}


def register_coordinator(entry: EnphaseConfigEntry) -> None:
    """Add envoy coordinator to list for use by services."""
    entry_envoy: Envoy = entry.runtime_data.envoy
    if entry_envoy.serial_number:
        envoylist[entry_envoy.serial_number] = entry.runtime_data


def unregister_coordinator(entry: EnphaseConfigEntry) -> None:
    """Remove envoy coordinator from list for use by services."""
    entry_envoy: Envoy = entry.runtime_data.envoy
    if entry_envoy.serial_number:
        envoylist.pop(entry_envoy.serial_number)


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


async def setup_hass_services(hass: HomeAssistant) -> ServiceResponse:
    """Configure Home Assistant services for Enphase_Envoy."""

    if hass.services.async_services_for_domain(DOMAIN):
        return None

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
        SERVICE_GET_FIRMWARE,
        get_firmware,
        schema=SERVICE_GET_FIRMWARE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return None
