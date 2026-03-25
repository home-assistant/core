"""Support for Ness D8X/D16X zone states - represented as binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SIGNAL_ZONE_CHANGED, NessAlarmConfigEntry, ZoneChangedData
from .const import (
    CONF_ZONE_NAME,
    CONF_ZONE_NUMBER,
    DEFAULT_ZONE_TYPE,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NessAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ness Alarm binary sensor from config entry."""
    # Get zone subentries
    zone_subentries = filter(
        lambda subentry: subentry.subentry_type == SUBENTRY_TYPE_ZONE,
        entry.subentries.values(),
    )

    # Create entities from zone subentries
    for subentry in zone_subentries:
        zone_num: int = subentry.data[CONF_ZONE_NUMBER]
        zone_type: BinarySensorDeviceClass = subentry.data.get(
            CONF_TYPE, DEFAULT_ZONE_TYPE
        )
        zone_name: str | None = subentry.data.get(CONF_ZONE_NAME)

        async_add_entities(
            [
                NessZoneBinarySensor(
                    zone_id=zone_num,
                    zone_type=zone_type,
                    entry_id=entry.entry_id,
                    zone_name=zone_name,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class NessZoneBinarySensor(BinarySensorEntity):
    """Representation of an Ness alarm zone as a binary sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        zone_id: int,
        zone_type: BinarySensorDeviceClass,
        entry_id: str,
        zone_name: str | None = None,
    ) -> None:
        """Initialize the binary_sensor."""
        self._zone_id = zone_id
        self._attr_device_class = zone_type
        self._attr_is_on = False
        self._attr_unique_id = f"{entry_id}_zone_{zone_id}"
        self._attr_name = f"Zone {zone_id}"
        self._attr_device_info = DeviceInfo(
            name=zone_name or f"Zone {zone_id}",
            identifiers={(DOMAIN, self._attr_unique_id)},
        )

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
