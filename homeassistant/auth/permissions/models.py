"""Models for permissions."""
from typing import TYPE_CHECKING

import attr

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from homeassistant.helpers import entity_registry as ent_reg  # noqa: F401
    from homeassistant.helpers import device_registry as dev_reg  # noqa: F401


@attr.s(slots=True)
class PermissionLookup:
    """Class to hold data for permission lookups."""

    entity_registry = attr.ib(type="ent_reg.EntityRegistry")
    device_registry = attr.ib(type="dev_reg.DeviceRegistry")
