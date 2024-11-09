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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Airtouch5ConfigEntry
from .const import DOMAIN
from .entity import Airtouch5Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Airtouch5ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Airtouch 5 Cover entities."""
    client = config_entry.runtime_data

    # Each zone has a cover for its open percentage
    async_add_entities(
        Airtouch5ZoneOpenPercentage(
            client, zone, client.latest_zone_status[zone.zone_number].has_sensor
        )
        for zone in client.zones
    )


class Airtouch5ZoneOpenPercentage(CoverEntity, Airtouch5Entity):
    """How open the damper is in each zone."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_translation_key = "damper"

    # Zones with temperature sensors shouldn't be manually controlled.
    # We allow it but warn the user in the integration documentation.
    _attr_supported_features = (
        CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
    )

    def __init__(
        self, client: Airtouch5SimpleClient, zone_name: ZoneName, has_sensor: bool
    ) -> None:
        """Initialise the Cover Entity."""
        super().__init__(client)
        self._zone_name = zone_name

        self._attr_unique_id = f"zone_{zone_name.zone_number}_open_percentage"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"zone_{zone_name.zone_number}")},
            name=zone_name.zone_name,
            manufacturer="Polyaire",
            model="AirTouch 5",
        )

    @callback
    def _async_update_attrs(self, data: dict[int, ZoneStatusZone]) -> None:
        if self._zone_name.zone_number not in data:
            return
        status = data[self._zone_name.zone_number]

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
        power: ZoneSettingPower

        if position_percent == 0:
            power = ZoneSettingPower.SET_TO_OFF
        else:
            power = ZoneSettingPower.SET_TO_ON

        zcz = ZoneControlZone(
            self._zone_name.zone_number,
            ZoneSettingValue.SET_OPEN_PERCENTAGE,
            power,
            position_percent / 100.0,
        )

        packet = self._client.data_packet_factory.zone_control([zcz])
        await self._client.send_packet(packet)
