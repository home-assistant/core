"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""

from __future__ import annotations

from pyspcwebgw import SpcWebGateway
from pyspcwebgw.const import ZoneInput, ZoneType
from pyspcwebgw.zone import Zone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_API, SIGNAL_UPDATE_SENSOR


def _get_device_class(zone_type: ZoneType) -> BinarySensorDeviceClass | None:
    return {
        ZoneType.ALARM: BinarySensorDeviceClass.MOTION,
        ZoneType.ENTRY_EXIT: BinarySensorDeviceClass.OPENING,
        ZoneType.FIRE: BinarySensorDeviceClass.SMOKE,
        ZoneType.TECHNICAL: BinarySensorDeviceClass.POWER,
    }.get(zone_type)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SPC binary sensor."""
    if discovery_info is None:
        return
    api: SpcWebGateway = hass.data[DATA_API]
    async_add_entities(
        [
            SpcBinarySensor(zone)
            for zone in api.zones.values()
            if _get_device_class(zone.type)
        ]
    )


class SpcBinarySensor(BinarySensorEntity):
    """Representation of a sensor based on a SPC zone."""

    _attr_should_poll = False

    def __init__(self, zone: Zone) -> None:
        """Initialize the sensor device."""
        self._zone = zone
        self._attr_name = zone.name
        self._attr_device_class = _get_device_class(zone.type)

    async def async_added_to_hass(self) -> None:
        """Call for adding new entities."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_UPDATE_SENSOR.format(self._zone.id),
                self._update_callback,
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def is_on(self) -> bool:
        """Whether the device is switched on."""
        return self._zone.input == ZoneInput.OPEN
