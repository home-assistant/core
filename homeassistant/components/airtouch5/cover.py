"""Representation of the Damper for AirTouch 5 Devices."""
import logging
from typing import Any

from airtouch5py.airtouch5_simple_client import Airtouch5SimpleClient
from airtouch5py.packets.zone_control import (
    ZoneControlZone,
    ZoneSettingPower,
    ZoneSettingValue,
)
from airtouch5py.packets.zone_name import ZoneName
from airtouch5py.packets.zone_status import ZoneStatusZone

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import Airtouch5Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airtouch 5 Cover entities."""
    client: Airtouch5SimpleClient = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[CoverEntity] = []

    # Each zone has a cover for its open percentage
    for zone in client.zones:
        entities.append(Airtouch5ZoneOpenPercentage(client, zone))

    async_add_entities(entities)


class Airtouch5ZoneOpenPercentage(CoverEntity, Airtouch5Entity):
    """How open the damper is in each zone."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
    )

    def __init__(self, client: Airtouch5SimpleClient, name: ZoneName) -> None:
        """Initialise the Cover Entity."""
        super().__init__(client)
        self._name = name

        self._attr_unique_id = f"zone_{name.zone_number}_open_percentage"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"zone_{name.zone_number}")},
            name=name.zone_name,
            manufacturer="Polyaire",
            model="AirTouch 5",
        )

    @callback
    def _async_update_attrs(self, data: dict[int, ZoneStatusZone]) -> None:
        if self._name.zone_number not in data:
            return
        status = data[self._name.zone_number]

        self._attr_current_cover_position = int(status.open_percentage * 100)
        if status.open_percentage == 0:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add data updated listener after this object has been initialized."""
        await super().async_added_to_hass()
        self._client.zone_status_callbacks.append(self._async_update_attrs)
        self._async_update_attrs(self._client.latest_zone_status)

    async def async_will_remove_from_hass(self) -> None:
        """Remove data updated listener after this object has been initialized."""
        await super().async_will_remove_from_hass()
        self._client.zone_status_callbacks.remove(self._async_update_attrs)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the damper."""
        await self._set_cover_position(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close damper."""
        await self._set_cover_position(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Update the damper to a specific position."""

        if (position := kwargs.get(ATTR_POSITION)) is None:
            _LOGGER.debug("Argument `position` is missing in set_cover_position")
            return
        await self._set_cover_position(position)

    async def _set_cover_position(self, position_percent: float) -> None:
        zcz = ZoneControlZone(
            self._name.zone_number,
            ZoneSettingValue.SET_OPEN_PERCENTAGE,
            ZoneSettingPower.KEEP_POWER_STATE,
            position_percent / 100.0,
        )
        packet = self._client.data_packet_factory.zone_control([zcz])
        await self._client.send_packet(packet)
