"""Support for hunterdouglass_powerview sensors."""

from aiopvapi.resources.shade import factory as PvShade

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR,
    DEVICE_INFO,
    DOMAIN,
    PV_API,
    PV_ROOM_DATA,
    PV_SHADE_DATA,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_KIND,
    SHADE_BATTERY_LEVEL,
    SHADE_BATTERY_LEVEL_MAX,
    SHADE_BATTERY_SENSOR_EXCLUDE,
    SHADE_SIGNAL_STRENGTH,
)
from .entity import ShadeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas shades sensors."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    battery_entities = []
    signal_entities = []
    for raw_shade in shade_data.values():
        shade = PvShade(raw_shade, pv_request)
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        signal_entities.append(
            PowerViewShadeSignalSensor(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
        if SHADE_BATTERY_LEVEL not in shade.raw_data:
            continue
        # skip hardwired blinds
        if shade.raw_data[SHADE_BATTERY_KIND] in SHADE_BATTERY_SENSOR_EXCLUDE:
            continue
        battery_entities.append(
            PowerViewShadeBatterySensor(
                coordinator, device_info, room_name, shade, name_before_refresh
            )
        )
    async_add_entities(battery_entities)
    async_add_entities(signal_entities)


class PowerViewShadeBatterySensor(ShadeEntity, SensorEntity):
    """Representation of an shade battery charge sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self):
        """Name of the shade battery."""
        return f"{self._shade_name} Battery"

    @property
    def unique_id(self):
        """Shade battery Uniqueid."""
        return f"{self._unique_id}_charge"

    @property
    def native_value(self):
        """Get the current value in percentage."""
        return round(
            self._shade.raw_data[SHADE_BATTERY_LEVEL] / SHADE_BATTERY_LEVEL_MAX * 100
        )

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    @callback
    def _async_update_shade_from_group(self):
        """Update with new data from the coordinator."""
        if self.coordinator.data is None:
            # empty data as result of 204/423 return
            return
        self._shade.raw_data = self.coordinator.data[self._shade.id]
        self.async_write_ha_state()


class PowerViewShadeSignalSensor(ShadeEntity, SensorEntity):
    """Representation of an shade signal sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH

    @property
    def name(self):
        """Name of the shade signal sensor."""
        return f"{self._shade_name} Signal"

    @property
    def unique_id(self):
        """Shade signal sensor Uniqueid."""
        return f"{self._unique_id}_signal"

    @property
    def native_value(self):
        """Get the current value in percentage."""
        return round(self._shade.raw_data[SHADE_SIGNAL_STRENGTH] / 4 * 100)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    @callback
    def _async_update_shade_from_group(self):
        """Update with new data from the coordinator."""
        if self.coordinator.data is None:
            # empty data as result of 204/423 return
            return
        self._shade.raw_data = self.coordinator.data[self._shade.id]
        self.async_write_ha_state()
