"""Ecovacs util functions."""

from __future__ import annotations

from enum import Enum
import random
import string
from typing import TYPE_CHECKING

from deebot_client.events.station import State

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
)

if TYPE_CHECKING:
    from .controller import EcovacsController


def get_client_device_id(hass: HomeAssistant, self_hosted: bool) -> str:
    """Get client device id."""
    if self_hosted:
        return f"HA-{slugify(hass.config.location_name)}"

    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
    )


def get_supported_entitites(
    controller: EcovacsController,
    entity_class: type[EcovacsDescriptionEntity],
    descriptions: tuple[EcovacsCapabilityEntityDescription, ...],
) -> list[EcovacsEntity]:
    """Return all supported entities for all devices."""
    return [
        entity_class(device, capability, description)
        for device in controller.devices
        for description in descriptions
        if (capability := description.capability_fn(device.capabilities))
    ]


@callback
def get_name_key(enum: Enum) -> str:
    """Return the lower case name of the enum."""
    if enum is State.EMPTYING:
        # Will be fixed in the next major release of deebot-client
        return "emptying_dustbin"
    return enum.name.lower()


@callback
def get_options(enum: type[Enum]) -> list[str]:
    """Return the options for the enum."""
    return [get_name_key(option) for option in enum]
