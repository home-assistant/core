"""Models for permissions."""
from __future__ import annotations

from typing import TYPE_CHECKING

import attr

if TYPE_CHECKING:
    from homeassistant.helpers import (
        device_registry as dev_reg,
        entity_registry as ent_reg,
    )


@attr.s(slots=True)
class PermissionLookup:
    """Class to hold data for permission lookups."""

    entity_registry: ent_reg.EntityRegistry = attr.ib()
    device_registry: dev_reg.DeviceRegistry = attr.ib()
