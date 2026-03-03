"""Support for SolarEdge Monitoring API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiosolaredge import SolarEdge

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
    SolarEdgeStorageDataService,
)
from .types import SolarEdgeConfigEntry


@dataclass(frozen=True, kw_only=True)
class SolarEdgeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for SolarEdge."""

    json_key: str


SENSOR_TYPES = [
    SolarEdgeSensorEntityDescription(
        key="lifetime_energy",
        json_key="lifeTimeData",
        translation_key="lifetime_energy",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="energy_this_year",
        json_key="lastYearData",
        translation_key="energy_this_year",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="energy_this_month",
        json_key="lastMonthData",
        translation_key="energy_this_month",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="energy_today",
        json_key="lastDayData",
        translation_key="energy_today",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="current_power",
        json_key="currentPower",
        translation_key="current_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarEdgeSensorEntityDescription(
        key="site_details",
        json_key="status",
        translation_key="site_details",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="meters",
        json_key="meters",
        translation_key="meters",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="sensors",
        json_key="sensors",
        translation_key="sensors",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="gateways",
        json_key="gateways",
        translation_key="gateways",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="batteries",
        json_key="batteries",
        translation_key="batteries",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="inverters",
        json_key="inverters",
        translation_key="inverters",
        entity_registry_enabled_default=False,
    ),
    SolarEdgeSensorEntityDescription(
        key="power_consumption",
        json_key="LOAD",
        translation_key="power_consumption",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarEdgeSensorEntityDescription(
        key="solar_power",
        json_key="PV",
        translation_key="solar_power",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarEdgeSensorEntityDescription(
        key="grid_power",
        json_key="GRID",
        translation_key="grid_power",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarEdgeSensorEntityDescription(
        key="storage_power",
        json_key="STORAGE",
        translation_key="storage_power",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    SolarEdgeSensorEntityDescription(
        key="purchased_energy",
        json_key="Purchased",
        translation_key="purchased_energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="production_energy",
        json_key="Production",
        translation_key="production_energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="consumption_energy",
        json_key="Consumption",
        translation_key="consumption_energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="selfconsumption_energy",
        json_key="SelfConsumption",
        translation_key="selfconsumption_energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="feedin_energy",
        json_key="FeedIn",
        translation_key="feedin_energy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="storage_level",
        json_key="STORAGE",
        translation_key="storage_level",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SolarEdgeSensorEntityDescription(
        key="battery_charge_today",
        json_key="battery_charge_today",
        translation_key="battery_charge_today",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
    SolarEdgeSensorEntityDescription(
        key="battery_discharge_today",
        json_key="battery_discharge_today",
        translation_key="battery_discharge_today",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarEdgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add an solarEdge entry."""
    # Add sensor entities only if API key is configured
    if DATA_API_CLIENT not in entry.runtime_data:
        return

    api = entry.runtime_data[DATA_API_CLIENT]
    sensor_factory = SolarEdgeSensorFactory(hass, entry, entry.data[CONF_SITE_ID], api)
    for service in sensor_factory.all_services:
        service.async_setup()
        await service.coordinator.async_refresh()

    # After inventory is refreshed, conditionally set up the storage service
    # only if the site has batteries, to avoid unnecessary API polling.
    if sensor_factory.setup_storage_service():
        await sensor_factory.storage_service.coordinator.async_refresh()
    else:
        # If inventory failed initially, listen for successful refreshes
        # to set up the storage service once battery data becomes available.
        @callback
        def _inventory_updated() -> None:
            if sensor_factory.setup_storage_service():
                unsub()
                new_entities = []
                for desc in SENSOR_TYPES:
                    if desc.key in (
                        "battery_charge_today",
                        "battery_discharge_today",
                    ):
                        entity = sensor_factory.create_sensor(desc)
                        if entity is not None:
                            new_entities.append(entity)
                if new_entities:
                    async_add_entities(new_entities)

        unsub = sensor_factory.inventory_service.coordinator.async_add_listener(
            _inventory_updated
        )

    entities = []
    for sensor_type in SENSOR_TYPES:
        sensor = sensor_factory.create_sensor(sensor_type)
        if sensor is not None:
            entities.append(sensor)
    async_add_entities(entities)


class SolarEdgeSensorFactory:
    """Factory which creates sensors based on the sensor_key."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarEdgeConfigEntry,
        site_id: str,
        api: SolarEdge,
    ) -> None:
        """Initialize the factory."""

        details = SolarEdgeDetailsDataService(hass, config_entry, api, site_id)
        overview = SolarEdgeOverviewDataService(hass, config_entry, api, site_id)
        inventory = SolarEdgeInventoryDataService(hass, config_entry, api, site_id)
        flow = SolarEdgePowerFlowDataService(hass, config_entry, api, site_id)
        energy = SolarEdgeEnergyDetailsService(hass, config_entry, api, site_id)

        self.all_services: list[SolarEdgeDataService] = [
            details,
            overview,
            inventory,
            flow,
            energy,
        ]
        self.inventory_service = inventory

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

        # Only create the storage data service if batteries are present,
        # to avoid unnecessary API polling for sites without batteries.
        self.storage_service: SolarEdgeStorageDataService | None = None
        self._storage_args = (hass, config_entry, api, site_id)

    def setup_storage_service(self) -> bool:
        """Initialize the storage data service if batteries are detected.

        Returns True if the storage service was created, False otherwise.
        """
        if self.storage_service is not None:
            return True
        hass, config_entry, api, site_id = self._storage_args
        if not self.inventory_service.coordinator.last_update_success:
            return False
        battery_count = self.inventory_service.data.get("batteries", 0)
        if not battery_count:
            return False

        storage = SolarEdgeStorageDataService(hass, config_entry, api, site_id)
        self.storage_service = storage
        self.all_services.append(storage)

        for key in ("battery_charge_today", "battery_discharge_today"):
            self.services[key] = (SolarEdgeStorageEnergySensor, storage)

        storage.async_setup()
        return True

    def create_sensor(
        self, sensor_type: SolarEdgeSensorEntityDescription
    ) -> SolarEdgeSensorEntity | None:
        """Create and return a sensor based on the sensor_key."""
        if sensor_type.key not in self.services:
            return None
        sensor_class, service = self.services[sensor_type.key]

        return sensor_class(sensor_type, service)


class SolarEdgeSensorEntity(
    CoordinatorEntity[DataUpdateCoordinator[None]], SensorEntity
):
    """Abstract class for a solaredge sensor."""

    _attr_has_entity_name = True

    entity_description: SolarEdgeSensorEntityDescription

    def __init__(
        self,
        description: SolarEdgeSensorEntityDescription,
        data_service: SolarEdgeDataService,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_service.coordinator)
        self.entity_description = description
        self.data_service = data_service
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data_service.site_id)}, manufacturer="SolarEdge"
        )

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
        sensor_type: SolarEdgeSensorEntityDescription,
        data_service: SolarEdgeEnergyDetailsService,
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(sensor_type, data_service)

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
        description: SolarEdgeSensorEntityDescription,
        data_service: SolarEdgePowerFlowDataService,
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(description, data_service)

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


class SolarEdgeStorageEnergySensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API storage energy sensor."""

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.entity_description.json_key)
