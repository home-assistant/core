"""binary_sensor platform for Netis Router.

Provides connectivity status sensors:

  - **WAN online**: ``True`` when at least one WAN interface reports
    ``status == "online"`` (from ``mwan3.status``). Extra state attributes
    list per-interface status (wan1, wan_lte, etc.).
  - **LTE connected**: ``True`` when the LTE modem reports a data connection
    (``lte_connect == 1`` from ``lte_ubus.LteInfo``). May be unavailable on
    non-LTE router models.
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetisCoordinator
from .entity import NetisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Netis binary sensors."""
    coordinator: NetisCoordinator = entry.runtime_data
    entities: list[NetisBinarySensorEntity] = [
        NetisBinarySensorEntity(
            coordinator,
            unique_key="wan_online",
            name="WAN online",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            icon="mdi:earth",
            is_on=lambda d: d.wan_online,
            extra=lambda d: {
                iface: status for iface, status in (d.wan_interfaces or {}).items()
            },
        ),
        NetisBinarySensorEntity(
            coordinator,
            unique_key="lte_connected",
            name="LTE connected",
            device_class=BinarySensorDeviceClass.CONNECTIVITY,
            icon="mdi:signal-cellular-3",
            is_on=lambda d: d.lte_connected,
        ),
    ]
    async_add_entities(entities)


class NetisBinarySensorEntity(NetisEntity, BinarySensorEntity):
    """Configurable binary sensor bound to a snapshot field."""

    def __init__(
        self,
        coordinator: NetisCoordinator,
        *,
        unique_key: str,
        name: str,
        is_on,
        extra=None,
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{unique_key}"
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._is_on = is_on
        self._extra = extra

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        return self._is_on(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None or self._extra is None:
            return None
        return self._extra(self.coordinator.data)
