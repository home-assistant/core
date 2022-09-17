"""Support for voltage, power & energy sensors for VeSync outlets."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.vesyncfan import VeSyncAirBypass
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncSwitch

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .common import VeSyncBaseEntity
from .const import DEV_TYPE_TO_HA, DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_SENSORS

_LOGGER = logging.getLogger(__name__)


@dataclass
class VeSyncSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], StateType]


@dataclass
class VeSyncSensorEntityDescription(
    SensorEntityDescription, VeSyncSensorEntityDescriptionMixin
):
    """Describe VeSync sensor entity."""

    exists_fn: Callable[
        [VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], bool
    ] = lambda _: True
    update_fn: Callable[
        [VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch], None
    ] = lambda _: None


def update_energy(device):
    """Update outlet details and energy usage."""
    device.update()
    device.update_energy()


def sku_supported(device, supported):
    """Get the base device of which a device is an instance."""
    return SKU_TO_BASE_DEVICE.get(device.device_type) in supported


def ha_dev_type(device):
    """Get the homeassistant device_type for a given device."""
    return DEV_TYPE_TO_HA.get(device.device_type)


FILTER_LIFE_SUPPORTED = ["LV-PUR131S", "Core200S", "Core300S", "Core400S", "Core600S"]
AIR_QUALITY_SUPPORTED = ["LV-PUR131S", "Core300S", "Core400S", "Core600S"]
PM25_SUPPORTED = ["Core300S", "Core400S", "Core600S"]

SENSORS: tuple[VeSyncSensorEntityDescription, ...] = (
    VeSyncSensorEntityDescription(
        key="filter-life",
        name="Filter Life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.filter_life,
        exists_fn=lambda device: sku_supported(device, FILTER_LIFE_SUPPORTED),
    ),
    VeSyncSensorEntityDescription(
        key="air-quality",
        name="Air Quality",
        value_fn=lambda device: device.details["air_quality"],
        exists_fn=lambda device: sku_supported(device, AIR_QUALITY_SUPPORTED),
    ),
    VeSyncSensorEntityDescription(
        key="pm25",
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.details["air_quality_value"],
        exists_fn=lambda device: sku_supported(device, PM25_SUPPORTED),
    ),
    VeSyncSensorEntityDescription(
        key="power",
        name="current power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.details["power"],
        update_fn=update_energy,
        exists_fn=lambda device: ha_dev_type(device) == "outlet",
    ),
    VeSyncSensorEntityDescription(
        key="energy",
        name="energy use today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.energy_today,
        update_fn=update_energy,
        exists_fn=lambda device: ha_dev_type(device) == "outlet",
    ),
    VeSyncSensorEntityDescription(
        key="energy-weekly",
        name="energy use weekly",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.weekly_energy_total,
        update_fn=update_energy,
        exists_fn=lambda device: ha_dev_type(device) == "outlet",
    ),
    VeSyncSensorEntityDescription(
        key="energy-monthly",
        name="energy use monthly",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.monthly_energy_total,
        update_fn=update_energy,
        exists_fn=lambda device: ha_dev_type(device) == "outlet",
    ),
    VeSyncSensorEntityDescription(
        key="energy-yearly",
        name="energy use yearly",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda device: device.yearly_energy_total,
        update_fn=update_energy,
        exists_fn=lambda device: ha_dev_type(device) == "outlet",
    ),
    VeSyncSensorEntityDescription(
        key="voltage",
        name="current voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.details["voltage"],
        update_fn=update_energy,
        exists_fn=lambda device: ha_dev_type(device) == "outlet",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_SENSORS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_SENSORS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        for description in SENSORS:
            if description.exists_fn(dev):
                entities.append(VeSyncSensorEntity(dev, description))
    async_add_entities(entities, update_before_add=True)


class VeSyncSensorEntity(VeSyncBaseEntity, SensorEntity):
    """Representation of a sensor describing a VeSync device."""

    entity_description: VeSyncSensorEntityDescription

    def __init__(
        self,
        device: VeSyncAirBypass | VeSyncOutlet | VeSyncSwitch,
        description: VeSyncSensorEntityDescription,
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_name = f"{super().name} {description.name}"
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)

    def update(self) -> None:
        """Run the update function defined for the sensor."""
        return self.entity_description.update_fn(self.device)
