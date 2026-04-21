"""Implement Enphase Envoy service actions."""

from __future__ import annotations

import logging
from typing import Any

from pyenphase import Envoy
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import EnphaseConfigEntry, EnphaseUpdateCoordinator

ACTION_COORDINATORS = "action_coordinators"

ATTR_ENVOY_DEVICE_ID = "device_id"

ACTION_TOKEN_LIFETIME = "token_lifetime"
ACTION_TOKEN_LIFETIME_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENVOY_DEVICE_ID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


def _find_envoy_coordinator(
    hass: HomeAssistant, device_id: str | None
) -> EnphaseUpdateCoordinator | None:
    """Find envoy coordinator.

    Returns coordinator for specified device_id. If device has
    parent, parent device will be used to find coordinator. If no
    device_id is specified, the first coordinator in the list is returned.
    """
    dev_reg = dr.async_get(hass)
    action_coordinators: dict[str, EnphaseUpdateCoordinator] = hass.data[DOMAIN][
        ACTION_COORDINATORS
    ]

    # find the device coordinator
    if device_id and (device_entry := dev_reg.async_get(device_id)):
        if device_entry.serial_number and (
            coordinator := action_coordinators.get(device_entry.serial_number)
        ):
            return coordinator
        # if child device was passed, use parent
        if (
            device_entry.via_device_id
            and (via_device := dev_reg.async_get(device_entry.via_device_id))
            and via_device.serial_number
            and (coordinator := action_coordinators.get(via_device.serial_number))
        ):
            return coordinator

    # use first entry if no specific id was specified and only 1 exists
    if device_id is None and len(action_coordinators) == 1:
        return next(iter(action_coordinators.values()))

    return None


def add_envoy_to_coordinators_list(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> None:
    """Add Envoy config entry to list of known envoy coordinators."""
    # keep track of our coordinator
    if (entry_envoy := entry.runtime_data.envoy) and entry_envoy.serial_number:
        hass.data[DOMAIN][ACTION_COORDINATORS][entry_envoy.serial_number] = (
            entry.runtime_data
        )


def remove_envoy_from_coordinators_list(
    hass: HomeAssistant, entry: EnphaseConfigEntry
) -> None:
    """Remove Envoy config entry from list of known envoy coordinators."""
    if (entry_envoy := entry.runtime_data.envoy) and entry_envoy.serial_number:
        hass.data[DOMAIN][ACTION_COORDINATORS].pop(entry_envoy.serial_number, None)


@callback
def setup_envoy_service_actions(hass: HomeAssistant) -> None:
    """Configure Home Assistant services for Enphase_Envoy."""

    async def token_lifetime_action(call: ServiceCall) -> dict[str, Any]:
        """Inspect action sends get request to Envoy and returns reply."""
        device_id = call.data.get(ATTR_ENVOY_DEVICE_ID)
        if not (coordinator := _find_envoy_coordinator(hass, device_id)):
            translation_key = (
                "envoy_token_lifetime_service_envoy_not_found"
                if device_id
                else "envoy_token_lifetime_service_no_device_id"
            )
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders={
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
        _LOGGER.debug(
            "Service action %s for Envoy %s found %s",
            call.service,
            envoy.serial_number,
            coordinator.token_lifetime,
        )
        return {
            "lifetime": coordinator.token_lifetime,
        }

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if ACTION_COORDINATORS not in hass.data[DOMAIN]:
        hass.data[DOMAIN][ACTION_COORDINATORS] = dict[str, EnphaseUpdateCoordinator]()

    # if services are already registered by another envoy don't define again
    existing = hass.services.async_services_for_domain(DOMAIN)
    if ACTION_TOKEN_LIFETIME not in existing:
        # declare service actions
        hass.services.async_register(
            DOMAIN,
            ACTION_TOKEN_LIFETIME,
            token_lifetime_action,
            schema=ACTION_TOKEN_LIFETIME_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
