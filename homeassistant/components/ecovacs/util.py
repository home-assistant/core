"""Ecovacs util functions."""
from __future__ import annotations

import random
import string
from typing import TYPE_CHECKING

from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
)

if TYPE_CHECKING:
    from .controller import EcovacsController


def get_client_device_id() -> str:
    """Get client device id."""
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(8)
    )


def get_supported_entitites(
    controller: EcovacsController,
    entity_class: type[EcovacsDescriptionEntity],
    descriptions: tuple[EcovacsCapabilityEntityDescription, ...],
) -> list[EcovacsEntity]:
    """Return all supported entities for all devices."""
    entities: list[EcovacsEntity] = []

    for device in controller.devices:
        for description in descriptions:
            if capability := description.capability_fn(device.capabilities):
                entities.append(entity_class(device, capability, description))

    return entities
