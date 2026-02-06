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
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import SIGNAL_ZONE_CHANGED, NessAlarmConfigEntry, ZoneChangedData
from .const import (
    CONF_ZONE_ID,
    CONF_ZONE_NAME,
    CONF_ZONE_NUMBER,
    CONF_ZONE_TYPE,
    CONF_ZONES,
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
                    subentry=subentry,
                    zone_name=zone_name,
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


async def async_setup_platform(  # pragma: no cover
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ness Alarm binary sensor devices (deprecated YAML)."""
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
        self,
        zone_id: int,
        zone_type: BinarySensorDeviceClass,
        entry_id: str | None = None,
        subentry=None,
        name: str | None = None,
        zone_name: str | None = None,
    ) -> None:
        """Initialize the binary_sensor."""
        self._zone_id = zone_id
        self._attr_device_class = zone_type
        self._attr_is_on = False

        # Config entry setup (has unique_id and device)
        if entry_id is not None:
            self._attr_has_entity_name = True
            self._attr_name = None
            self._attr_unique_id = f"{entry_id}_zone_{zone_id}"

            # Create device info for this zone (makes it a separate device)
            # Use zone_name if provided (from YAML import), otherwise default to "Zone {zone_id}"
            device_name = zone_name if zone_name else f"Zone {zone_id}"
            self._attr_device_info = DeviceInfo(
                name=device_name,
                identifiers={(DOMAIN, self._attr_unique_id)},
            )
        else:  # pragma: no cover
            # YAML setup (no unique_id, for backward compatibility)
            self._attr_name = name

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
