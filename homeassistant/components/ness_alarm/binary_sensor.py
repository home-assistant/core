"""Support for Ness D8X/D16X zone states - represented as binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_TYPE,
    CONF_ZONES,
    SIGNAL_ZONE_CHANGED,
    ZoneChangedData,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ness Alarm binary sensor devices."""
    if not discovery_info:
        return

    configured_zones = discovery_info[CONF_ZONES]

    async_add_entities(
        NessZoneBinarySensor(
            zone_id=zone_config[CONF_ZONE_ID],
            name=zone_config[CONF_ZONE_NAME],
            zone_type=zone_config[CONF_ZONE_TYPE],
        )
        for zone_config in configured_zones
    )


class NessZoneBinarySensor(BinarySensorEntity):
    """Representation of an Ness alarm zone as a binary sensor."""

    _attr_should_poll = False

    def __init__(
        self, zone_id: int, name: str, zone_type: BinarySensorDeviceClass
    ) -> None:
        """Initialize the binary_sensor."""
        self._zone_id = zone_id
        self._attr_name = name
        self._attr_device_class = zone_type
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_ZONE_CHANGED, self._handle_zone_change
            )
        )

    @callback
    def _handle_zone_change(self, data: ZoneChangedData) -> None:
        """Handle zone state update."""
        if self._zone_id == data.zone_id:
            self._attr_is_on = data.state
            self.async_write_ha_state()
