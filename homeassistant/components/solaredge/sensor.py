"""Support for SolarEdge Monitoring API."""
from __future__ import annotations

from typing import Any

from solaredge import Solaredge

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_BATTERY, DEVICE_CLASS_POWER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SITE_ID, DATA_API_CLIENT, DOMAIN, SENSOR_TYPES
from .coordinator import (
    SolarEdgeDataService,
    SolarEdgeDetailsDataService,
    SolarEdgeEnergyDetailsService,
    SolarEdgeInventoryDataService,
    SolarEdgeOverviewDataService,
    SolarEdgePowerFlowDataService,
)
from .models import SolarEdgeSensor


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
                type[SolarEdgeSensor | SolarEdgeOverviewSensor], SolarEdgeDataService
            ],
        ] = {"site_details": (SolarEdgeDetailsSensor, details)}

        for key in [
            "lifetime_energy",
            "energy_this_year",
            "energy_this_month",
            "energy_today",
            "current_power",
        ]:
            self.services[key] = (SolarEdgeOverviewSensor, overview)

        for key in ["meters", "sensors", "gateways", "batteries", "inverters"]:
            self.services[key] = (SolarEdgeInventorySensor, inventory)

        for key in ["power_consumption", "solar_power", "grid_power", "storage_power"]:
            self.services[key] = (SolarEdgePowerFlowSensor, flow)

        for key in ["storage_level"]:
            self.services[key] = (SolarEdgeStorageLevelSensor, flow)

        for key in [
            "purchased_power",
            "production_power",
            "feedin_power",
            "consumption_power",
            "selfconsumption_power",
        ]:
            self.services[key] = (SolarEdgeEnergyDetailsSensor, energy)

    def create_sensor(self, sensor_type: SolarEdgeSensor) -> SolarEdgeSensor:
        """Create and return a sensor based on the sensor_key."""
        sensor_class, service = self.services[sensor_type.key]

        return sensor_class(self.platform_name, sensor_type, service)


class SolarEdgeSensorEntity(CoordinatorEntity, SensorEntity):
    """Abstract class for a solaredge sensor."""

    def __init__(
        self,
        platform_name: str,
        sensor_type: SolarEdgeSensor,
        data_service: SolarEdgeDataService,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_service.coordinator)
        self.platform_name = platform_name
        self.sensor_type = sensor_type
        self.data_service = data_service

        self._attr_device_class = sensor_type.device_class
        self._attr_entity_registry_enabled_default = (
            sensor_type.entity_registry_enabled_default
        )
        self._attr_icon = sensor_type.icon
        self._attr_last_reset = sensor_type.last_reset
        self._attr_name = f"{platform_name} ({sensor_type.name})"
        self._attr_state_class = sensor_type.state_class
        self._attr_unit_of_measurement = sensor_type.unit_of_measurement


class SolarEdgeOverviewSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API overview sensor."""

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.sensor_type.json_key)


class SolarEdgeDetailsSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API details sensor."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data


class SolarEdgeInventorySensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API inventory sensor."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self.sensor_type.json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.sensor_type.json_key)


class SolarEdgeEnergyDetailsSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    def __init__(self, platform_name, sensor_type, data_service):
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_type, data_service)

        self._attr_unit_of_measurement = data_service.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self.sensor_type.json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.sensor_type.json_key)


class SolarEdgePowerFlowSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    _attr_device_class = DEVICE_CLASS_POWER

    def __init__(
        self,
        platform_name: str,
        sensor_type: SolarEdgeSensor,
        data_service: SolarEdgeDataService,
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_type, data_service)

        self._attr_unit_of_measurement = data_service.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self.sensor_type.json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self.sensor_type.json_key)


class SolarEdgeStorageLevelSensor(SolarEdgeSensorEntity):
    """Representation of an SolarEdge Monitoring API storage level sensor."""

    _attr_device_class = DEVICE_CLASS_BATTERY

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        attr = self.data_service.attributes.get(self.sensor_type.json_key)
        if attr and "soc" in attr:
            return attr["soc"]
        return None
