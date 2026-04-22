"""Support for Lutron Caseta Occupancy/Vacancy/Battery Sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pylutron_caseta import OCCUPANCY_GROUP_OCCUPIED

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import ATTR_SUGGESTED_AREA, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .const import CONFIG_URL, MANUFACTURER, UNASSIGNED_AREA
from .entity import LutronCasetaEntity
from .models import LutronCasetaConfigEntry, LutronCasetaData
from .util import area_name_from_id

SCAN_INTERVAL = timedelta(days=1)
BATTERY_STATUS_GOOD = "good"
BATTERY_STATUS_LOW = "low"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta binary_sensor platform.

    Adds occupancy groups and shade battery status from the Caseta bridge
    associated with the config_entry as binary_sensor entities.
    """
    data = config_entry.runtime_data
    bridge = data.bridge
    occupancy_groups = bridge.occupancy_groups
    async_add_entities(
        LutronOccupancySensor(occupancy_group, data)
        for occupancy_group in occupancy_groups.values()
    )
    async_add_entities(
        (
            LutronCasetaBatterySensor(device, data)
            for device in bridge.get_devices_by_domain(COVER_DOMAIN)
        ),
        update_before_add=True,
    )


class LutronOccupancySensor(LutronCasetaEntity, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, device, data):
        """Init an occupancy sensor."""
        super().__init__(device, data)
        area = area_name_from_id(self._smartbridge.areas, device["area"])
        name = f"{area} {device['device_name']}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model="Lutron Occupancy",
            name=self.name,
            via_device=(DOMAIN, self._bridge_device["serial"]),
            configuration_url=CONFIG_URL,
            entry_type=DeviceEntryType.SERVICE,
        )
        if area != UNASSIGNED_AREA:
            self._attr_device_info[ATTR_SUGGESTED_AREA] = area

    @property
    def is_on(self) -> bool:
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self._bridge_unique_id}_{self.device_id}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"device_id": self.device_id}


class LutronCasetaBatterySensor(LutronCasetaEntity, BinarySensorEntity):
    """Representation of a Lutron Caseta shade low battery sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(self, device: dict[str, Any], data: LutronCasetaData) -> None:
        """Initialize the battery sensor."""
        super().__init__(device, data)
        # The base entity sets the shade name; remove it so the battery device
        # class provides the sensor name.
        if hasattr(self, "_attr_name"):
            delattr(self, "_attr_name")
        self._attr_is_on: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the battery sensor."""
        return f"{super().unique_id}_battery"

    # pylint: disable-next=hass-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Skip bridge subscriptions; the battery sensor is polled."""

    async def async_update(self) -> None:
        """Fetch the latest battery status from the bridge."""
        status = await self._smartbridge.get_battery_status(self.device_id)
        normalized_status = status.strip().casefold() if status else None
        if normalized_status == BATTERY_STATUS_LOW:
            self._attr_is_on = True
        elif normalized_status == BATTERY_STATUS_GOOD:
            self._attr_is_on = False
        else:
            self._attr_is_on = None
