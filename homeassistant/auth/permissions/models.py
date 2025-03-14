"""Models for permissions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import attr

if TYPE_CHECKING:
    from homeassistant.helpers import device_registry as dr, entity_registry as er


@attr.s(slots=True)
class PermissionLookup:
    """Class to hold data for permission lookups."""

    entity_registry: er.EntityRegistry = attr.ib()
    device_registry: dr.DeviceRegistry = attr.ib()
