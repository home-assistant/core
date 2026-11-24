"""Sensor platform for the NEPViewer integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from aionepviewer import Device, DeviceStatisticsOverview, Module, SiteOverview

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import NepViewerConfigEntry, NepViewerCoordinator
from .entity import NepViewerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NepViewerSensorEntityDescription[_DataT](SensorEntityDescription):
    """Describes a NEPViewer sensor."""

    value_fn: Callable[[_DataT], float]


SITE_SENSOR_DESCRIPTIONS: tuple[NepViewerSensorEntityDescription[SiteOverview], ...] = (
    NepViewerSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.energy.pv_panel.power,
    ),
    NepViewerSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.today,
    ),
    NepViewerSensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.total,
    ),
)

DEVICE_SENSOR_DESCRIPTIONS: tuple[
    NepViewerSensorEntityDescription[DeviceStatisticsOverview], ...
] = (
    NepViewerSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.total_now,
    ),
    NepViewerSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.today,
    ),
    NepViewerSensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.total,
    ),
)

MODULE_SENSOR_DESCRIPTIONS: tuple[NepViewerSensorEntityDescription[Module], ...] = (
    NepViewerSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.now,
    ),
    NepViewerSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.today_power,
    ),
    NepViewerSensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_power,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NepViewerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NEPViewer sensors from a config entry."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        NepViewerSiteSensorEntity(coordinator, site.sid, description)
        for site in coordinator.sites
        for description in SITE_SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        NepViewerDeviceSensorEntity(coordinator, device.sn, description)
        for device in coordinator.devices
        for description in DEVICE_SENSOR_DESCRIPTIONS
    )
    panels = [
        (device, plc_sn)
        for device in sorted(coordinator.devices, key=lambda device: device.sn)
        for plc_sn in sorted(coordinator.data.device_modules.get(device.sn, {}))
    ]
    entities.extend(
        NepViewerModuleSensorEntity(coordinator, device, plc_sn, description, number)
        for number, (device, plc_sn) in enumerate(panels, start=1)
        for description in MODULE_SENSOR_DESCRIPTIONS
    )
    async_add_entities(entities)


class NepViewerSiteSensorEntity(NepViewerEntity, SensorEntity):
    """A sensor entity for a NEPViewer site."""

    entity_description: NepViewerSensorEntityDescription[SiteOverview]

    @property
    @override
    def native_value(self) -> float:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data.site_overviews[self._identifier]
        )


class NepViewerDeviceSensorEntity(NepViewerEntity, SensorEntity):
    """A sensor entity for a NEPViewer gateway or microinverter."""

    entity_description: NepViewerSensorEntityDescription[DeviceStatisticsOverview]

    @property
    @override
    def native_value(self) -> float:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data.device_overviews[self._identifier]
        )


class NepViewerModuleSensorEntity(NepViewerEntity, SensorEntity):
    """A sensor entity for a single panel (PLC module) of a microinverter."""

    entity_description: NepViewerSensorEntityDescription[Module]

    def __init__(
        self,
        coordinator: NepViewerCoordinator,
        device: Device,
        plc_sn: str,
        description: NepViewerSensorEntityDescription[Module],
        number: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, plc_sn, description)
        self._device_sn = device.sn
        site_detail = coordinator.site_details.get(device.sid)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, plc_sn)},
            translation_key="panel",
            translation_placeholders={"number": str(number)},
            manufacturer=(site_detail and site_detail.pv_remark) or None,
            model=(site_detail and site_detail.panel_model) or None,
            serial_number=plc_sn,
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, device.sn),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )

    @property
    @override
    def available(self) -> bool:
        """Return if the panel is still reported by the API."""
        return (
            super().available
            and self._identifier
            in self.coordinator.data.device_modules.get(self._device_sn, {})
        )

    @property
    @override
    def native_value(self) -> float:
        """Return the sensor value."""
        return self.entity_description.value_fn(
            self.coordinator.data.device_modules[self._device_sn][self._identifier]
        )
