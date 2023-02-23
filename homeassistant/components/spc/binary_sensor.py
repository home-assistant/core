"""Support for Vanderbilt (formerly Siemens) SPC alarm systems."""
from __future__ import annotations

from pyspcwebgw import SpcWebGateway
from pyspcwebgw.const import ZoneInput, ZoneType
from pyspcwebgw.zone import Zone

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SIGNAL_UPDATE_SENSOR


def _get_device_class(zone_type: ZoneType) -> BinarySensorDeviceClass | None:
    return {
        ZoneType.ALARM: BinarySensorDeviceClass.MOTION,
        ZoneType.ENTRY_EXIT: BinarySensorDeviceClass.OPENING,
        ZoneType.FIRE: BinarySensorDeviceClass.SMOKE,
        ZoneType.TECHNICAL: BinarySensorDeviceClass.POWER,
    }.get(zone_type)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SPC binary sensor."""
    api: SpcWebGateway = hass.data[DOMAIN][config_entry.entry_id]
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
        self._attr_unique_id = zone.id

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
    def name(self) -> str:
        """Return the name of the device."""
        return self._zone.name

    @property
    def is_on(self) -> bool:
        """Whether the device is switched on."""
        return self._zone.input == ZoneInput.OPEN

    @property
    def device_class(self) -> BinarySensorDeviceClass | None:
        """Return the device class."""
        return _get_device_class(self._zone.type)
