"""Support for hunterdouglass_powerview sensors."""
from aiopvapi.resources.shade import BaseShade, factory as PvShade

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
    ATTR_SIGNAL_STRENGTH,
    ATTR_SIGNAL_STRENGTH_MAX,
    DOMAIN,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_LEVEL,
    SHADE_BATTERY_LEVEL_MAX,
)
from .entity import ShadeEntity
from .model import PowerviewEntryData


class PowerViewSensor(ShadeEntity, SensorEntity):
    """Representation of an shade battery charge sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    @callback
    def _async_update_shade_from_group(self) -> None:
        """Update with new data from the coordinator."""
        self._shade.raw_data = self.data.get_raw_data(self._shade.id)
        self.async_write_ha_state()


class PowerViewShadeBatterySensor(PowerViewSensor):
    """Representation of an shade battery charge sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._attr_unique_id}_charge"
        self._attr_name = f"{self._shade_name} Battery"

    @property
    def native_value(self) -> int:
        """Get the current value in percentage."""
        return round(
            self._shade.raw_data[SHADE_BATTERY_LEVEL] / SHADE_BATTERY_LEVEL_MAX * 100
        )

    async def async_update(self) -> None:
        """Refresh shade battery."""
        await self._shade.refresh_battery()


class PowerViewShadeSignalSensor(PowerViewSensor):
    """Representation of an shade signal sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device_info, room_name, shade, name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self._attr_unique_id = f"{self._attr_unique_id}_signal"
        self._attr_name = f"{self._shade_name} Signal"

    @property
    def native_value(self) -> int:
        """Get the current value in percentage."""
        return round(
            self._shade.raw_data[ATTR_SIGNAL_STRENGTH] / ATTR_SIGNAL_STRENGTH_MAX * 100
        )

    async def async_update(self) -> None:
        """Refresh signal strength."""
        await self._shade.refresh()


SENSOR_TYPES = {
    PowerViewShadeBatterySensor: SHADE_BATTERY_LEVEL,
    PowerViewShadeSignalSensor: ATTR_SIGNAL_STRENGTH,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas shades sensors."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities: list[PowerViewSensor] = []
    for raw_shade in pv_entry.shade_data.values():
        shade: BaseShade = PvShade(raw_shade, pv_entry.api)
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = pv_entry.room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        for cls, attr in SENSOR_TYPES.items():
            if attr in shade.raw_data:
                entities.append(
                    cls(
                        pv_entry.coordinator,
                        pv_entry.device_info,
                        room_name,
                        shade,
                        name_before_refresh,
                    )
                )
    async_add_entities(entities)
