"""A risco entity base class."""

from typing import Any, override

from pyrisco import RiscoCloud
from pyrisco.cloud.zone import Zone as CloudZone
from pyrisco.local.zone import Zone as LocalZone

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import cloud_update_signal, zone_update_signal
from .const import DOMAIN
from .models import CloudData


def zone_unique_id(risco: RiscoCloud, zone_id: int) -> str:
    """Return unique id for a cloud zone."""
    return f"{risco.site_uuid}_zone_{zone_id}"


class RiscoCloudEntity(Entity):
    """Risco cloud entity base class."""

    _attr_should_poll = False

    def __init__(self, *, cloud_data: CloudData, entry_id: str, **kwargs: Any) -> None:
        """Init the entity."""
        super().__init__(**kwargs)
        self._cloud_data = cloud_data
        self._entry_id = entry_id

    @property
    def _risco(self) -> RiscoCloud:
        """Return the Risco API object."""
        return self._cloud_data.system

    @callback
    def _handle_update(self) -> None:
        """Handle a state update from the cloud."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, cloud_update_signal(self._entry_id), self._handle_update
            )
        )


class RiscoZoneEntity(Entity):
    """Risco zone entity base class, shared by cloud and local."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        device_unique_id: str,
        suffix: str,
        zone_id: int,
        zone: CloudZone | LocalZone,
        **kwargs: Any,
    ) -> None:
        """Init the zone."""
        super().__init__(**kwargs)
        self._zone_id = zone_id
        self._zone = zone
        self._attr_unique_id = f"{device_unique_id}{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_unique_id)},
            manufacturer="Risco",
            name=zone.name,
        )
        self._attr_extra_state_attributes = {"zone_id": zone_id}


class RiscoCloudZoneEntity(RiscoZoneEntity, RiscoCloudEntity):
    """Risco cloud zone entity base class."""

    def __init__(
        self,
        *,
        cloud_data: CloudData,
        entry_id: str,
        suffix: str,
        zone_id: int,
        zone: CloudZone,
        **kwargs: Any,
    ) -> None:
        """Init the zone."""
        device_unique_id = zone_unique_id(cloud_data.system, zone_id)
        super().__init__(
            cloud_data=cloud_data,
            entry_id=entry_id,
            device_unique_id=device_unique_id,
            suffix=suffix,
            zone_id=zone_id,
            zone=zone,
            **kwargs,
        )

    @callback
    def _handle_update(self) -> None:
        self._zone = self._cloud_data.alarm.zones[self._zone_id]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()


class RiscoLocalZoneEntity(RiscoZoneEntity):
    """Risco local zone entity base class."""

    def __init__(
        self,
        *,
        system_id: str,
        suffix: str,
        zone_id: int,
        zone: LocalZone,
        **kwargs: Any,
    ) -> None:
        """Init the zone."""
        device_unique_id = f"{system_id}_zone_{zone_id}_local"
        super().__init__(
            device_unique_id=device_unique_id,
            suffix=suffix,
            zone_id=zone_id,
            zone=zone,
            **kwargs,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, zone_update_signal(self._zone_id), self.async_write_ha_state
            )
        )
