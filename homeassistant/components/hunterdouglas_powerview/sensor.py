"""Support for hunterdouglass_powerview sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from aiopvapi.resources.shade import BaseShade, factory as PvShade

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_KIND,
    ATTR_SIGNAL_STRENGTH,
    ATTR_SIGNAL_STRENGTH_MAX,
    BATTERY_KIND_HARDWIRED,
    DOMAIN,
    ROOM_ID_IN_SHADE,
    ROOM_NAME_UNICODE,
    SHADE_BATTERY_LEVEL,
    SHADE_BATTERY_LEVEL_MAX,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import ShadeEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData


@dataclass
class PowerviewSensorDescriptionMixin:
    """Mixin to describe a Sensor entity."""

    update_fn: Callable[[BaseShade], Any]
    native_value_fn: Callable[[BaseShade], int]
    create_sensor_fn: Callable[[BaseShade], bool]


@dataclass
class PowerviewSensorDescription(
    SensorEntityDescription, PowerviewSensorDescriptionMixin
):
    """Class to describe a Sensor entity."""

    entity_category = EntityCategory.DIAGNOSTIC
    state_class = SensorStateClass.MEASUREMENT


SENSORS: Final = [
    PowerviewSensorDescription(
        key="charge",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        native_value_fn=lambda shade: round(
            shade.raw_data[SHADE_BATTERY_LEVEL] / SHADE_BATTERY_LEVEL_MAX * 100
        ),
        create_sensor_fn=lambda shade: bool(
            shade.raw_data.get(ATTR_BATTERY_KIND) != BATTERY_KIND_HARDWIRED
            and SHADE_BATTERY_LEVEL in shade.raw_data
        ),
        update_fn=lambda shade: shade.refresh_battery(),
    ),
    PowerviewSensorDescription(
        key="signal",
        name="Signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=PERCENTAGE,
        native_value_fn=lambda shade: round(
            shade.raw_data[ATTR_SIGNAL_STRENGTH] / ATTR_SIGNAL_STRENGTH_MAX * 100
        ),
        create_sensor_fn=lambda shade: bool(ATTR_SIGNAL_STRENGTH in shade.raw_data),
        update_fn=lambda shade: shade.refresh(),
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the hunter douglas sensor entities."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    entities: list[PowerViewSensor] = []
    for raw_shade in pv_entry.shade_data.values():
        shade: BaseShade = PvShade(raw_shade, pv_entry.api)
        name_before_refresh = shade.name
        room_id = shade.raw_data.get(ROOM_ID_IN_SHADE)
        room_name = pv_entry.room_data.get(room_id, {}).get(ROOM_NAME_UNICODE, "")

        for description in SENSORS:
            if description.create_sensor_fn(shade):
                entities.append(
                    PowerViewSensor(
                        pv_entry.coordinator,
                        pv_entry.device_info,
                        room_name,
                        shade,
                        name_before_refresh,
                        description,
                    )
                )

    async_add_entities(entities)


class PowerViewSensor(ShadeEntity, SensorEntity):
    """Representation of an shade sensor."""

    entity_description: PowerviewSensorDescription

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        name: str,
        description: PowerviewSensorDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device_info, room_name, shade, name)
        self.entity_description = description
        self._attr_name = f"{self._shade_name} {description.name}"
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> int:
        """Get the current value in percentage."""
        return self.entity_description.native_value_fn(self._shade)

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

    async def async_update(self) -> None:
        """Refresh sensor entity."""
        await self.entity_description.update_fn(self._shade)
        self.async_write_ha_state()
