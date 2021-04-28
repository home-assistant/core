"""Support for SolarEdge Monitoring API."""
from __future__ import annotations

from abc import abstractmethod
from datetime import date, datetime, timedelta
import logging
from typing import Any

from requests.exceptions import ConnectTimeout, HTTPError
from solaredge import Solaredge
from stringcase import snakecase

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, DEVICE_CLASS_BATTERY, DEVICE_CLASS_POWER
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_SITE_ID,
    DETAILS_UPDATE_DELAY,
    ENERGY_DETAILS_DELAY,
    INVENTORY_UPDATE_DELAY,
    OVERVIEW_UPDATE_DELAY,
    POWER_FLOW_UPDATE_DELAY,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add an solarEdge entry."""
    # Add the needed sensors to hass
    api = Solaredge(entry.data[CONF_API_KEY])

    # Check if api can be reached and site is active
    try:
        response = await hass.async_add_executor_job(
            api.get_details, entry.data[CONF_SITE_ID]
        )
        if response["details"]["status"].lower() != "active":
            _LOGGER.error("SolarEdge site is not active")
            return
        _LOGGER.debug("Credentials correct and site is active")
    except KeyError as ex:
        _LOGGER.error("Missing details data in SolarEdge response")
        raise ConfigEntryNotReady from ex
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Could not retrieve details from SolarEdge API")
        raise ConfigEntryNotReady from ex

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

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return SENSOR_TYPES[self.sensor_key][2]

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self.platform_name} ({SENSOR_TYPES[self.sensor_key][1]})"

    @property
    def icon(self) -> str | None:
        """Return the sensor icon."""
        return SENSOR_TYPES[self.sensor_key][3]


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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self._json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self._json_key)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self.data_service.unit


class SolarEdgePowerFlowSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API power flow sensor."""

    def __init__(
        self, platform_name: str, sensor_key: str, data_service: SolarEdgeDataService
    ) -> None:
        """Initialize the power flow sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    @property
    def device_class(self) -> str:
        """Device Class."""
        return DEVICE_CLASS_POWER

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.data_service.attributes.get(self._json_key)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self.data_service.data.get(self._json_key)

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self.data_service.unit


class SolarEdgeStorageLevelSensor(SolarEdgeSensor):
    """Representation of an SolarEdge Monitoring API storage level sensor."""

    def __init__(
        self, platform_name: str, sensor_key: str, data_service: SolarEdgeDataService
    ) -> None:
        """Initialize the storage level sensor."""
        super().__init__(platform_name, sensor_key, data_service)

        self._json_key = SENSOR_TYPES[self.sensor_key][0]

    @property
    def device_class(self) -> str:
        """Return the device_class of the device."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        attr = self.data_service.attributes.get(self._json_key)
        if attr and "soc" in attr:
            return attr["soc"]
        return None


class SolarEdgeDataService:
    """Get and update the latest data."""

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the data object."""
        self.api = api
        self.site_id = site_id

        self.data = {}
        self.attributes = {}

        self.hass = hass
        self.coordinator = None

    @callback
    def async_setup(self) -> None:
        """Coordinator creation."""
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=str(self),
            update_method=self.async_update_data,
            update_interval=self.update_interval,
        )

    @property
    @abstractmethod
    def update_interval(self) -> timedelta:
        """Update interval."""

    @abstractmethod
    def update(self) -> None:
        """Update data in executor."""

    async def async_update_data(self) -> None:
        """Update data."""
        await self.hass.async_add_executor_job(self.update)


class SolarEdgeOverviewDataService(SolarEdgeDataService):
    """Get and update the latest overview data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return OVERVIEW_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_overview(self.site_id)
            overview = data["overview"]
        except KeyError as ex:
            raise UpdateFailed("Missing overview data, skipping update") from ex

        self.data = {}

        for key, value in overview.items():
            if key in ["lifeTimeData", "lastYearData", "lastMonthData", "lastDayData"]:
                data = value["energy"]
            elif key in ["currentPower"]:
                data = value["power"]
            else:
                data = value
            self.data[key] = data

        _LOGGER.debug("Updated SolarEdge overview: %s", self.data)


class SolarEdgeDetailsDataService(SolarEdgeDataService):
    """Get and update the latest details data."""

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the details data service."""
        super().__init__(hass, api, site_id)

        self.data = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return DETAILS_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""

        try:
            data = self.api.get_details(self.site_id)
            details = data["details"]
        except KeyError as ex:
            raise UpdateFailed("Missing details data, skipping update") from ex

        self.data = None
        self.attributes = {}

        for key, value in details.items():
            key = snakecase(key)

            if key in ["primary_module"]:
                for module_key, module_value in value.items():
                    self.attributes[snakecase(module_key)] = module_value
            elif key in [
                "peak_power",
                "type",
                "name",
                "last_update_time",
                "installation_date",
            ]:
                self.attributes[key] = value
            elif key == "status":
                self.data = value

        _LOGGER.debug("Updated SolarEdge details: %s, %s", self.data, self.attributes)


class SolarEdgeInventoryDataService(SolarEdgeDataService):
    """Get and update the latest inventory data."""

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return INVENTORY_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_inventory(self.site_id)
            inventory = data["Inventory"]
        except KeyError as ex:
            raise UpdateFailed("Missing inventory data, skipping update") from ex

        self.data = {}
        self.attributes = {}

        for key, value in inventory.items():
            self.data[key] = len(value)
            self.attributes[key] = {key: value}

        _LOGGER.debug("Updated SolarEdge inventory: %s, %s", self.data, self.attributes)


class SolarEdgeEnergyDetailsService(SolarEdgeDataService):
    """Get and update the latest power flow data."""

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the power flow data service."""
        super().__init__(hass, api, site_id)

        self.unit = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return ENERGY_DETAILS_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            now = datetime.now()
            today = date.today()
            midnight = datetime.combine(today, datetime.min.time())
            data = self.api.get_energy_details(
                self.site_id,
                midnight,
                now.strftime("%Y-%m-%d %H:%M:%S"),
                meters=None,
                time_unit="DAY",
            )
            energy_details = data["energyDetails"]
        except KeyError as ex:
            raise UpdateFailed("Missing power flow data, skipping update") from ex

        if "meters" not in energy_details:
            _LOGGER.debug(
                "Missing meters in energy details data. Assuming site does not have any"
            )
            return

        self.data = {}
        self.attributes = {}
        self.unit = energy_details["unit"]

        for meter in energy_details["meters"]:
            if "type" not in meter or "values" not in meter:
                continue
            if meter["type"] not in [
                "Production",
                "SelfConsumption",
                "FeedIn",
                "Purchased",
                "Consumption",
            ]:
                continue
            if len(meter["values"][0]) == 2:
                self.data[meter["type"]] = meter["values"][0]["value"]
                self.attributes[meter["type"]] = {"date": meter["values"][0]["date"]}

        _LOGGER.debug(
            "Updated SolarEdge energy details: %s, %s", self.data, self.attributes
        )


class SolarEdgePowerFlowDataService(SolarEdgeDataService):
    """Get and update the latest power flow data."""

    def __init__(self, hass: HomeAssistant, api: Solaredge, site_id: str) -> None:
        """Initialize the power flow data service."""
        super().__init__(hass, api, site_id)

        self.unit = None

    @property
    def update_interval(self) -> timedelta:
        """Update interval."""
        return POWER_FLOW_UPDATE_DELAY

    def update(self) -> None:
        """Update the data from the SolarEdge Monitoring API."""
        try:
            data = self.api.get_current_power_flow(self.site_id)
            power_flow = data["siteCurrentPowerFlow"]
        except KeyError as ex:
            raise UpdateFailed("Missing power flow data, skipping update") from ex

        power_from = []
        power_to = []

        if "connections" not in power_flow:
            _LOGGER.debug(
                "Missing connections in power flow data. Assuming site does not have any"
            )
            return

        for connection in power_flow["connections"]:
            power_from.append(connection["from"].lower())
            power_to.append(connection["to"].lower())

        self.data = {}
        self.attributes = {}
        self.unit = power_flow["unit"]

        for key, value in power_flow.items():
            if key in ["LOAD", "PV", "GRID", "STORAGE"]:
                self.data[key] = value["currentPower"]
                self.attributes[key] = {"status": value["status"]}

            if key in ["GRID"]:
                export = key.lower() in power_to
                self.data[key] *= -1 if export else 1
                self.attributes[key]["flow"] = "export" if export else "import"

            if key in ["STORAGE"]:
                charge = key.lower() in power_to
                self.data[key] *= -1 if charge else 1
                self.attributes[key]["flow"] = "charge" if charge else "discharge"
                self.attributes[key]["soc"] = value["chargeLevel"]

        _LOGGER.debug(
            "Updated SolarEdge power flow: %s, %s", self.data, self.attributes
        )
