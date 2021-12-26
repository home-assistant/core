"""Support for hunterdouglass_powerview sensors."""
import logging

from aiopvapi.resources.shade import factory as PvShade

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import DEVICE_CLASS_SIGNAL_STRENGTH, PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory

from .const import (
    CONF_IMPORT_BATTERY_SENSOR,
    CONF_IMPORT_SIGNAL_STRENGTH,
    COORDINATOR,
    DEFAULT_IMPORT_BATTERY_SENSOR,
    DEFAULT_IMPORT_SIGNAL_STRENGTH,
    DEVICE_INFO,
    DOMAIN,
    PV_API,
    PV_ROOM_DATA,
    PV_SHADE_DATA,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_KIND,
    SHADE_BATTERY_KIND_EXCLUDE,
    SHADE_BATTERY_LEVEL,
    SHADE_BATTERY_LEVEL_MAX,
)
from .entity import ShadeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hunter douglas shades sensors."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    room_data = pv_data[PV_ROOM_DATA]
    shade_data = pv_data[PV_SHADE_DATA]
    pv_request = pv_data[PV_API]
    coordinator = pv_data[COORDINATOR]
    device_info = pv_data[DEVICE_INFO]

    battery_sensors = entry.options.get(
        CONF_IMPORT_BATTERY_SENSOR, DEFAULT_IMPORT_BATTERY_SENSOR
    )
    signal_sensors = entry.options.get(
        CONF_IMPORT_SIGNAL_STRENGTH, DEFAULT_IMPORT_SIGNAL_STRENGTH
    )

    if battery_sensors is False:
        _LOGGER.debug("Excluding battery sensors based on config entry")
    if signal_sensors is False:
        _LOGGER.debug("Excluding signal sensors based on config entry")

    entities = []
    for raw_shade in shade_data.values():
        shade = PvShade(raw_shade, pv_request)
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")
        if signal_sensors is True:
            entities.append(
                PowerViewShadeSignalSensor(
                    coordinator, device_info, room_name, shade, name_before_refresh
                )
            )
        if SHADE_BATTERY_LEVEL not in shade.raw_data:
            continue
        # skip hardwired blinds
        if shade.raw_data[SHADE_BATTERY_KIND] in SHADE_BATTERY_KIND_EXCLUDE:
            continue
        if battery_sensors is True:
            entities.append(
                PowerViewShadeBatterySensor(
                    coordinator, device_info, room_name, shade, name_before_refresh
                )
            )
    async_add_entities(entities)


class PowerViewShadeBatterySensor(ShadeEntity, SensorEntity):
    """Representation of an shade battery charge sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def name(self):
        """Name of the shade battery."""
        return f"{self._shade_name} Battery"

    @property
    def device_class(self):
        """Shade battery Class."""
        return SensorDeviceClass.BATTERY

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
        self._shade.raw_data = self.coordinator.data[self._shade.id]
        self.async_write_ha_state()


class PowerViewShadeSignalSensor(ShadeEntity, SensorEntity):
    """Representation of an shade signal sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def name(self):
        """Name of the shade signal sensor."""
        return f"{self._shade_name} Signal"

    @property
    def device_class(self):
        """Shade signal sensor Class."""
        return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def unique_id(self):
        """Shade signal sensor Uniqueid."""
        return f"{self._unique_id}_signal"

    @property
    def state(self):
        """Get the current value in percentage."""
        return round(self._shade.raw_data["signalStrength"] / 4 * 100)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_update_shade_from_group)
        )

    @callback
    def _async_update_shade_from_group(self):
        """Update with new data from the coordinator."""
        self._shade.raw_data = self.coordinator.data[self._shade.id]
        self.async_write_ha_state()
