"""A risco entity base class."""
from __future__ import annotations

from typing import Any

from pyrisco.common import Zone

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RiscoDataUpdateCoordinator, zone_update_signal
from .const import DOMAIN


def zone_unique_id(risco, zone_id: int) -> str:
    """Return unique id for a cloud zone."""
    return f"{risco.site_uuid}_zone_{zone_id}"


class RiscoCloudEntity(CoordinatorEntity[RiscoDataUpdateCoordinator]):
    """Risco cloud entity base class."""

    def __init__(
        self, *, coordinator: RiscoDataUpdateCoordinator, **kwargs: Any
    ) -> None:
        """Init the entity."""
        super().__init__(coordinator=coordinator, **kwargs)

    def _get_data_from_coordinator(self) -> None:
        raise NotImplementedError

    def _refresh_from_coordinator(self) -> None:
        self._get_data_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._refresh_from_coordinator)
        )

    @property
    def _risco(self):
        """Return the Risco API object."""
        return self.coordinator.risco


class RiscoCloudZoneEntity(RiscoCloudEntity):
    """Risco cloud zone entity base class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: RiscoDataUpdateCoordinator,
        name: str | None,
        suffix: str,
        zone_id: int,
        zone: Zone,
        **kwargs: Any,
    ) -> None:
        """Init the zone."""
        super().__init__(coordinator=coordinator, **kwargs)
        self._zone_id = zone_id
        self._zone = zone
        self._attr_name = name
        device_unique_id = zone_unique_id(self._risco, zone_id)
        self._attr_unique_id = f"{device_unique_id}{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            manufacturer="Risco",
            name=self._zone.name,
        )
        self._attr_extra_state_attributes = {"zone_id": zone_id}

    def _get_data_from_coordinator(self) -> None:
        self._zone = self.coordinator.data.zones[self._zone_id]


class RiscoLocalZoneEntity(Entity):
    """Risco local zone entity base class."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        system_id: str,
        name: str | None,
        suffix: str,
        zone_id: int,
        zone: Zone,
        **kwargs: Any,
    ) -> None:
        """Init the zone."""
        super().__init__(**kwargs)
        self._zone_id = zone_id
        self._zone = zone
        self._attr_name = name
        device_unique_id = f"{system_id}_zone_{zone_id}_local"
        self._attr_unique_id = f"{device_unique_id}{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            manufacturer="Risco",
            name=zone.name,
        )
        self._attr_extra_state_attributes = {"zone_id": zone_id}

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        signal = zone_update_signal(self._zone_id)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, self.async_write_ha_state)
        )
