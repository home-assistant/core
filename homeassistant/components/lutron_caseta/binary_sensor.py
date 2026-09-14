"""Support for Lutron Caseta Occupancy/Vacancy/Battery Sensors."""

import asyncio
from datetime import timedelta
from typing import Any, override

from pylutron_caseta import (
    OCCUPANCY_GROUP_OCCUPIED,
    BridgeDisconnectedError,
    BridgeResponseError,
)
from pylutron_caseta.smartbridge import Smartbridge

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import ATTR_SUGGESTED_AREA, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
        LutronOccupancySensor(hass, occupancy_group, data)
        for occupancy_group in occupancy_groups.values()
    )
    battery_sensors = [
        LutronCasetaBatterySensor(hass, cover, data)
        for cover in bridge.get_devices_by_domain(COVER_DOMAIN)
    ]
    reports_battery = await asyncio.gather(
        *(
            _async_reports_battery(bridge, sensor.device_id)
            for sensor in battery_sensors
        )
    )
    entity_registry = er.async_get(hass)
    sensors_to_add: list[LutronCasetaBatterySensor] = []
    for sensor, has_battery in zip(battery_sensors, reports_battery, strict=True):
        if has_battery:
            sensors_to_add.append(sensor)
        elif entity_id := entity_registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, sensor.unique_id
        ):
            # Earlier releases created this for every cover
            entity_registry.async_remove(entity_id)

    async_add_entities(sensors_to_add, update_before_add=True)


async def _async_reports_battery(bridge: Smartbridge, device_id: str) -> bool:
    """Return whether the bridge reports a battery for the device.

    A shade wired for power answers without a battery status, and nothing in
    the device data the bridge caches tells the two apart. A cover the bridge
    could not answer for keeps its sensor, so nothing is removed over a hiccup.
    """
    try:
        return await bridge.get_battery_status(device_id) is not None
    except BridgeResponseError, BridgeDisconnectedError, TimeoutError:
        return True


class LutronOccupancySensor(LutronCasetaEntity, BinarySensorEntity):
    """Representation of a Lutron occupancy group."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self, hass: HomeAssistant, device: dict[str, Any], data: LutronCasetaData
    ) -> None:
        """Init an occupancy sensor."""
        super().__init__(hass, device, data)
        area = area_name_from_id(self._smartbridge.areas, device["area"])
        name = f"{area} {device['device_name']}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer=MANUFACTURER,
            model="Lutron Occupancy",
            name=name,
            via_device_id=dr.async_get_device_id_by_identifier(
                hass,
                (DOMAIN, self._bridge_device["serial"]),
                config_entry_id=data.config_entry_id,
            ),
            configuration_url=CONFIG_URL,
            entry_type=DeviceEntryType.SERVICE,
        )
        if area != UNASSIGNED_AREA:
            self._attr_device_info[ATTR_SUGGESTED_AREA] = area

    @property
    @override
    def is_on(self) -> bool:
        """Return the brightness of the light."""
        return self._device["status"] == OCCUPANCY_GROUP_OCCUPIED

    @override
    # pylint: disable-next=home-assistant-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._smartbridge.add_occupancy_subscriber(
            self.device_id, self.async_write_ha_state
        )

    @property
    @override
    def device_id(self):
        """Return the device ID used for calling pylutron_caseta."""
        return self._device["occupancy_group_id"]

    @property
    @override
    def unique_id(self):
        """Return a unique identifier."""
        return f"occupancygroup_{self._bridge_unique_id}_{self.device_id}"

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {"device_id": self.device_id}


class LutronCasetaBatterySensor(LutronCasetaEntity, BinarySensorEntity):
    """Representation of a Lutron Caseta shade low battery sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(
        self, hass: HomeAssistant, device: dict[str, Any], data: LutronCasetaData
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(hass, device, data)
        # The base entity sets the shade name; remove it so the battery device
        # class provides the sensor name.
        if hasattr(self, "_attr_name"):
            delattr(self, "_attr_name")
        self._attr_is_on: bool | None = None

    @property
    @override
    def unique_id(self) -> str:
        """Return the unique ID of the battery sensor."""
        return f"{super().unique_id}_battery"

    @override
    # pylint: disable-next=home-assistant-missing-super-call
    async def async_added_to_hass(self) -> None:
        """Skip bridge subscriptions; the battery sensor is polled."""

    async def async_update(self) -> None:
        """Fetch the latest battery status from the bridge."""
        try:
            status = await self._smartbridge.get_battery_status(self.device_id)
        except BridgeResponseError, BridgeDisconnectedError, TimeoutError:
            self._attr_is_on = None
            return
        normalized_status = status.strip().casefold() if status else None
        if normalized_status == BATTERY_STATUS_LOW:
            self._attr_is_on = True
        elif normalized_status == BATTERY_STATUS_GOOD:
            self._attr_is_on = False
        else:
            self._attr_is_on = None
