"""Shared base entity and device info for Netis platforms.

All platform entities (sensor, binary_sensor, switch, select, button,
device_tracker) inherit from :class:`NetisEntity` which:

* Links the entity to the coordinator (so it auto-updates on each poll).
* Attaches ``DeviceInfo`` so all entities are grouped under the router in
  HA's device registry.
* Sets ``_attr_has_entity_name = True`` so entity names are prefixed with
  the device name (e.g. "Netis 192.168.1.1 - Uptime").
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import NetisCoordinator


def router_device_info(coordinator: NetisCoordinator) -> DeviceInfo:
    """Build DeviceInfo for the router itself.

    Pulls model / firmware / hardware version from the latest coordinator
    data snapshot so the device card in HA shows accurate information.
    """
    data = coordinator.data
    model = data.model if data else None
    sw = data.firmware if data else None
    hw = data.hardware_version if data else None
    return DeviceInfo(
        # Use the config entry ID as the unique device identifier so the
        # device survives entity name changes and reloads.
        identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
        name=f"Netis {coordinator.config_entry.title}",
        manufacturer=MANUFACTURER,
        model=model or "Router",
        sw_version=sw,
        hw_version=hw,
    )


class NetisEntity(CoordinatorEntity[NetisCoordinator], Entity):
    """Base entity that points at the router device.

    Subclass this for any platform entity that reads from the coordinator.
    Set ``_attr_name``, ``_attr_unique_id``, and platform-specific attributes
    in the subclass ``__init__``.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetisCoordinator) -> None:
        """Initialise the base entity with coordinator and device info."""
        super().__init__(coordinator)
        self._attr_device_info = router_device_info(coordinator)
