"""Sensor platform for the NEPViewer integration."""

from collections.abc import Callable
from dataclasses import dataclass

from aionepviewer.models.device import Device, DeviceStatisticsOverview
from aionepviewer.models.module import Module
from aionepviewer.models.site import Site, SiteOverview

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NepViewerConfigEntry
from .const import DOMAIN
from .coordinator import NepViewerCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NepViewerSiteSensorEntityDescription(SensorEntityDescription):
    """Describes a NEPViewer site sensor."""

    value_fn: Callable[[SiteOverview], float]


@dataclass(frozen=True, kw_only=True)
class NepViewerDeviceSensorEntityDescription(SensorEntityDescription):
    """Describes a NEPViewer device sensor."""

    value_fn: Callable[[DeviceStatisticsOverview], float]


@dataclass(frozen=True, kw_only=True)
class NepViewerModuleSensorEntityDescription(SensorEntityDescription):
    """Describes a NEPViewer panel (module) sensor."""

    value_fn: Callable[[Module], float]


SITE_SENSOR_DESCRIPTIONS: tuple[NepViewerSiteSensorEntityDescription, ...] = (
    NepViewerSiteSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.energy.pv_panel.power,
    ),
    NepViewerSiteSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.today,
    ),
    NepViewerSiteSensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.total,
    ),
)

DEVICE_SENSOR_DESCRIPTIONS: tuple[NepViewerDeviceSensorEntityDescription, ...] = (
    NepViewerDeviceSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.total_now,
    ),
    NepViewerDeviceSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.today,
    ),
    NepViewerDeviceSensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.production.total,
    ),
)

MODULE_SENSOR_DESCRIPTIONS: tuple[NepViewerModuleSensorEntityDescription, ...] = (
    NepViewerModuleSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.now,
    ),
    NepViewerModuleSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.today_power,
    ),
    NepViewerModuleSensorEntityDescription(
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
        NepViewerSiteSensorEntity(coordinator, site, description)
        for site in coordinator.data.sites
        for description in SITE_SENSOR_DESCRIPTIONS
    ]
    entities += [
        NepViewerDeviceSensorEntity(coordinator, device, description)
        for device in coordinator.data.devices
        for description in DEVICE_SENSOR_DESCRIPTIONS
    ]
    devices_by_sn = {d.sn: d for d in coordinator.data.devices}
    panel_num = 1
    for device_sn in sorted(coordinator.data.device_modules):
        device = devices_by_sn.get(device_sn)
        if device is None:
            continue
        for plc_sn in sorted(coordinator.data.device_modules[device_sn]):
            module = coordinator.data.device_modules[device_sn][plc_sn]
            for description in MODULE_SENSOR_DESCRIPTIONS:
                entities.append(
                    NepViewerModuleSensorEntity(
                        coordinator, device, module, description, panel_num
                    )
                )
            panel_num += 1
    async_add_entities(entities)


class NepViewerSiteSensorEntity(CoordinatorEntity[NepViewerCoordinator], SensorEntity):
    """A sensor entity for a NEPViewer site (virtual device)."""

    _attr_has_entity_name = True
    entity_description: NepViewerSiteSensorEntityDescription

    def __init__(
        self,
        coordinator: NepViewerCoordinator,
        site: Site,
        description: NepViewerSiteSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._site = site
        self._attr_unique_id = f"{site.sid}_{description.key}"
        site_detail = coordinator.data.site_details.get(site.sid)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, site.sid)},
            name=site.site_name,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=(site_detail and site_detail.company_name) or "NEP",
            serial_number=(site_detail and site_detail.project_reference_id) or None,
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        overview = self.coordinator.data.site_overviews.get(self._site.sid)
        if overview is None:
            return None
        return self.entity_description.value_fn(overview)


class NepViewerDeviceSensorEntity(
    CoordinatorEntity[NepViewerCoordinator], SensorEntity
):
    """A sensor entity for a physical NEPViewer device (gateway)."""

    _attr_has_entity_name = True
    entity_description: NepViewerDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: NepViewerCoordinator,
        device: Device,
        description: NepViewerDeviceSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        self._attr_unique_id = f"{device.sn}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.sn)},
            name=device.alias or device.sn,
            manufacturer="NEP",
            model=device.model_name or None,
            serial_number=device.sn,
            sw_version=" / ".join(
                filter(None, [device.cpu_version, device.wifi_version])
            )
            or None,
            via_device=(DOMAIN, device.sid),
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        overview = self.coordinator.data.device_overviews.get(self._device.sn)
        if overview is None:
            return None
        return self.entity_description.value_fn(overview)


class NepViewerModuleSensorEntity(
    CoordinatorEntity[NepViewerCoordinator], SensorEntity
):
    """A sensor entity for a single panel (PLC module) under a microinverter."""

    _attr_has_entity_name = True
    entity_description: NepViewerModuleSensorEntityDescription

    def __init__(
        self,
        coordinator: NepViewerCoordinator,
        device: Device,
        module: Module,
        description: NepViewerModuleSensorEntityDescription,
        panel_num: int,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device = device
        self._module = module
        self._attr_unique_id = f"{module.plc_sn}_{description.key}"
        site_detail = coordinator.data.site_details.get(device.sid)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, module.plc_sn)},
            name=f"Panel {panel_num}",
            manufacturer=(site_detail and site_detail.pv_remark) or None,
            model=(site_detail and site_detail.panel_model) or None,
            serial_number=module.plc_sn,
            via_device=(DOMAIN, device.sn),
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        device_modules = self.coordinator.data.device_modules.get(self._device.sn, {})
        module = device_modules.get(self._module.plc_sn)
        if module is None:
            return None
        return self.entity_description.value_fn(module)
