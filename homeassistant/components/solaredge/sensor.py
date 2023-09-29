"""Support for SolarEdge Monitoring API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solaredge import Solaredge

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_SITE_ID, DATA_API_CLIENT, DOMAIN
from .coordinator import (
    SolarEdgeDataService,
    SolarEdgeDetailsDataService,
    SolarEdgeEnergyDetailsService,
    SolarEdgeInventoryDataService,
    SolarEdgeOverviewDataService,
    SolarEdgePowerFlowDataService,
)


@dataclass
class SolarEdgeSensorEntityRequiredKeyMixin:
    """Sensor entity description with json_key for SolarEdge."""

    json_key: str


@dataclass
class SolarEdgeSensorEntityDescription(
    SensorEntityDescription, SolarEdgeSensorEntityRequiredKeyMixin
):
    """Sensor entity description for SolarEdge."""


SENSOR_TYPES = [
    SolarEdgeSensorEntityDescription(
        key="lifetime_energy",
        json_key="lifeTimeData",
        name="Lifetime energy",
        icon="mdi:solar-power",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="energy_this_year",
        json_key="lastYearData",
        name="Energy this year",
        entity_registry_enabled_default=False,
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="energy_this_month",
        json_key="lastMonthData",
        name="Energy this month",
        entity_registry_enabled_default=False,
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="energy_today",
        json_key="lastDayData",
        name="Energy today",
        entity_registry_enabled_default=False,
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="current_power",
        json_key="currentPower",
        name="Current Power",
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarEdgeSensorEntityDescription(
        key="site_details",
        json_key="status",
        name="Site details",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="meters",
        json_key="meters",
        name="Meters",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="sensors",
        json_key="sensors",
        name="Sensors",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="gateways",
        json_key="gateways",
        name="Gateways",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="batteries",
        json_key="batteries",
        name="Batteries",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="inverters",
        json_key="inverters",
        name="Inverters",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="power_consumption",
        json_key="LOAD",
        name="Power Consumption",
        entity_registry_enabled_default=False,
        icon="mdi:flash",
    ),
    SolarEdgeSensorEntityDescription(
        key="solar_power",
        json_key="PV",
        name="Solar Power",
        entity_registry_enabled_default=False,
        icon="mdi:solar-power",
    ),
    SolarEdgeSensorEntityDescription(
        key="grid_power",
        json_key="GRID",
        name="Grid Power",
        entity_registry_enabled_default=False,
        icon="mdi:power-plug",
    ),
    SolarEdgeSensorEntityDescription(
        key="storage_power",
        json_key="STORAGE",
        name="Storage Power",
        entity_registry_enabled_default=False,
        icon="mdi:car-battery",
    ),
    SolarEdgeSensorEntityDescription(
        key="purchased_energy",
        json_key="Purchased",
        name="Imported Energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="production_energy",
        json_key="Production",
        name="Production Energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="consumption_energy",
        json_key="Consumption",
        name="Consumption Energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="selfconsumption_energy",
        json_key="SelfConsumption",
        name="SelfConsumption Energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="feedin_energy",
        json_key="FeedIn",
        name="Exported Energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="storage_level",
        json_key="STORAGE",
        name="Storage Level",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an solarEdge entry."""
    # Add the needed sensors to hass
    api: Solaredge = hass.data[DOMAIN][entry.entry_id][DATA_API_CLIENT]

    sensor_factory = SolarEdgeSensorFactory(
        hass, entry.title, entry.data[CONF_SITE_ID], api
    )
    for service in sensor_factory.all_services:
        service.async_setup()
        await service.coordinator.async_refresh()

    entities = []
    for sensor_type in SENSOR_TYPES:
        sensor = sensor_factory.create_sensor(sensor_type)
        if sensor is not None:
            entities.append(sensor)
    async_add_entities(entities)


class SolarEdgeSensorFactory:
    """Factory which creates sensors based on the sensor_key."""

    def __init__(
        self, hass: HomeAssistant, platform_name: str, site_id: str, api: Solaredge
    ) -> None:
        """Initialize the factory."""
        self.platform_name = platform_name

        details = SolarEdgeDetailsDataService(hass, api, site_id)
        overview = SolarEdgeOverviewDataService(hass, api, site_id)
        inventory = SolarEdgeInventoryDataService(hass, api, site_id)
        flow = SolarEdgePowerFlowDataService(hass, api, site_id)
        energy = SolarEdgeEnergyDetailsService(hass, api, site_id)

        self.all_services = (details, overview, inventory, flow, energy)

        self.services: dict[
            str,
            tuple[
                type[SolarEdgeSensorEntity | SolarEdgeOverviewSensor],
                SolarEdgeDataService,
            ],
        ] = {"site_details": (SolarEdgeDetailsSensor, details)}

        for key in (
            "lifetime_energy",
            "energy_this_year",
            "energy_this_month",
            "energy_today",
            "current_power",
        ):
            self.services[key] = (SolarEdgeOverviewSensor, overview)

        for key in ("meters", "sensors", "gateways", "batteries", "inverters"):
            self.services[key] = (SolarEdgeInventorySensor, inventory)

        for key in ("power_consumption", "solar_power", "grid_power", "storage_power"):
            self.services[key] = (SolarEdgePowerFlowSensor, flow)

        for key in ("storage_level",):
            self.services[key] = (SolarEdgeStorageLevelSensor, flow)

        for key in (
            "purchased_energy",
            "production_energy",
            "feedin_energy",
            "consumption_energy",
            "selfconsumption_energy",
        ):
            self.services[key] = (SolarEdgeEnergyDetailsSensor, energy)

    def create_sensor(
        self, sensor_type: SolarEdgeSensorEntityDescription
    ) -> SolarEdgeSensorEntity:
        """Create and return a sensor based on the sensor_key."""
        sensor_class, service = self.services[sensor_type.key]

        return sensor_class(self.platform_name, sensor_type, service)


class SolarEdgeSensorEntity(
    CoordinatorEntity[DataUpdateCoordinator[None]], SensorEntity
):
    """Abstract class for a solaredge sensor."""

    entity_description: SolarEdgeSensorEntityDescription

    def __init__(
        self,
        platform_name: str,
        description: SolarEdgeSensorEntityDescription,
        data_service: SolarEdgeDataService,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_service.coordinator)
        self.platform_name = platform_name
        self.entity_description = description
        self.data_service = data_service

        self._attr_name = f"{platform_name} ({description.name})"

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        if not self.data_service.site_id:
            return None
        return f"{self.data_service.site_id}_{self.entity_description.key}"


class SolarEdgeOverviewSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API overview sensor."""

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.entity_description.json_key)


class SolarEdgeDetailsSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API details sensor."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.entity_description.json_key)

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        if not self.data_service.site_id:
            return None
        return str(self.data_service.site_id)


class SolarEdgeInventorySensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API inventory sensor."""

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return self.data_service.attributes.get(self.entity_description.json_key)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.entity_description.json_key)


class SolarEdgeEnergyDetailsSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    def __init__(
        self,
        platform_name: str,
        sensor_type: SolarEdgeSensorEntityDescription,
        data_service: SolarEdgeEnergyDetailsService,
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_type, data_service)

        self._attr_native_unit_of_measurement = data_service.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return self.data_service.attributes.get(self.entity_description.json_key)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.entity_description.json_key)


class SolarEdgePowerFlowSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    _attr_device_class = SensorDeviceClass.POWER

    def __init__(
        self,
        platform_name: str,
        description: SolarEdgeSensorEntityDescription,
        data_service: SolarEdgePowerFlowDataService,
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(platform_name, description, data_service)

        self._attr_native_unit_of_measurement = data_service.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return self.data_service.attributes.get(self.entity_description.json_key)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.entity_description.json_key)


class SolarEdgeStorageLevelSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API storage level sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        attr = self.data_service.attributes.get(self.entity_description.json_key)
        if attr and "soc" in attr:
            return attr["soc"]
        return None
