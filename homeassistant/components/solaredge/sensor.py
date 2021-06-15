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
    for sensor_key in SENSOR_TYPES:
        sensor = sensor_factory.create_sensor(sensor_key)
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

    def create_sensor(self, sensor_key: str) -> SolarEdgeSensor:
        """Create and return a sensor based on the sensor_key."""
        sensor_class, service = self.services[sensor_key]

        return sensor_class(self.platform_name, sensor_key, service)


class SolarEdgeSensor(CoordinatorEntity, SensorEntity):
    """Abstract class for a solaredge sensor."""

    def __init__(
        self, platform_name: str, sensor_key: str, data_service: SolarEdgeDataService
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data_service.coordinator)
        self.platform_name = platform_name
        self.sensor_key = sensor_key
        self.data_service = data_service

        self._attr_unit_of_measurement = SENSOR_TYPES[sensor_key][2]
        self._attr_name = f"{platform_name} ({SENSOR_TYPES[sensor_key][1]})"
        self._attr_icon = SENSOR_TYPES[sensor_key][3]


class SolarEdgeOverviewSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API overview sensor."""

    def __init__(
        self, platform_name: str, sensor_key: str, data_service: SolarEdgeDataService
    ) -> None:
        """Initialize the overview sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self._json_key)


class SolarEdgeDetailsSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API details sensor."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data


class SolarEdgeInventorySensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API inventory sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the inventory sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self._json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self._json_key)


class SolarEdgeEnergyDetailsSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    def __init__(self, platform_name, sensor_key, data_service):
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]
        self._attr_unit_of_measurement = data_service.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self._json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self._json_key)


class SolarEdgePowerFlowSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    _attr_device_class = DEVICE_CLASS_POWER

    def __init__(
        self, platform_name: str, sensor_key: str, data_service: SolarEdgeDataService
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]
        self._attr_unit_of_measurement = data_service.unit

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self._json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self._json_key)


class SolarEdgeStorageLevelSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API storage level sensor."""

    _attr_device_class = DEVICE_CLASS_BATTERY

    def __init__(
        self, platform_name: str, sensor_key: str, data_service: SolarEdgeDataService
    ) -> None:
        """Initialize the storage level sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        attr = self.data_service.attributes.get(self._json_key)
        if attr and "soc" in attr:
            return attr["soc"]
        return None
