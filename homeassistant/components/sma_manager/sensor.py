"""SMA Manager Sensor Entities."""

from datetime import timedelta
import logging

# 3rd Party Imports
from sma_manager_api import SMA

# Home Assistant Imports
# pylint: disable=hass-component-root-import
from homeassistant.components.integration.const import METHOD_TRAPEZOIDAL
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

# Local Imports
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create and sets up the entities and setup Riemann Integral version of the same entities, so they can be used in the energy panel.

    @param hass:
    @param config_entry:
    @param async_add_entities:
    @return:
    """

    sma = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = Coordinator(hass, sma)
    device = DeviceInfo(
        identifiers={(DOMAIN, sma.serial_number)},
        name=sma.name,
        manufacturer="SMA",
        model="SMA Manager",
    )

    await coordinator.async_config_entry_first_refresh()

    # Create base entities
    base_entities = [
        GridConsumption(coordinator, sma, device),
        GridFeed(coordinator, sma, device),
        PhaseOneConsumption(coordinator, sma, device),
        PhaseOneFeed(coordinator, sma, device),
        PhaseTwoConsumption(coordinator, sma, device),
        PhaseTwoFeed(coordinator, sma, device),
        PhaseThreeConsumption(coordinator, sma, device),
        PhaseThreeFeed(coordinator, sma, device),
    ]
    async_add_entities(base_entities)

    # Create Integral Sensor for every base entity
    integral_entities = []
    for entity in base_entities:
        name = f"{entity.name} Energy"
        integral_entities.append(
            IntegrationSensor(
                integration_method=METHOD_TRAPEZOIDAL,
                name=name,
                round_digits=2,
                source_entity=f"sensor.{entity.unique_id}",
                unique_id=name.lower().replace(" ", "_"),
                unit_prefix="k",
                unit_time=UnitOfTime.HOURS,
            )
        )
    async_add_entities(integral_entities)


class Coordinator(DataUpdateCoordinator):
    """Coordinates data fetching from the API."""

    def __init__(self, hass: HomeAssistant, sma: SMA) -> None:
        """Init the coordinator object.

        @param hass:
        @param sma:
        """
        super().__init__(
            hass,
            _LOGGER,
            name="SMA Coordinator",
            update_interval=timedelta(seconds=sma.refresh_time),
        )
        self.sma = sma

    async def _async_update_data(self):
        """Refresh data from SMA Manager."""
        await self.sma.refresh_data()


class SensorBase(CoordinatorEntity, SensorEntity):
    """Base class for all sensors, any sensor should inherit from this class.

    @note: self._attr_name should be created in the child class prior to super().init() so the unique id can be generated
    """

    _attr_name: str
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    _device: DeviceInfo

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the coordinator object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        super().__init__(coordinator)

        # Generate unique id
        self._attr_unique_id = self._attr_name.lower().replace(" ", "_")

        self._sma = sma
        self._device = device

    @property
    def device_info(self) -> DeviceInfo:
        """Return information to link this entity with the correct device.

        @return:
        """
        return self._device

    @property
    def available(self) -> bool:
        """Gets the available state from sma object.

        @return:
        """
        return self._sma.available

    @property
    def native_value(self) -> float:
        """Native value of the sensor.

        Should be implemented by the child class
        """
        raise NotImplementedError


class GridConsumption(SensorBase):
    """Grid Consumption Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Grid Consumption object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Grid Consumption"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.grid_consumption

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.grid_consumption


class GridFeed(SensorBase):
    """Grid Feed Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Grid Feed object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Grid Feed"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.grid_feed

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.grid_feed


class PhaseOneConsumption(SensorBase):
    """Phase One Consumption Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Phase One Consumption object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Phase 1 Consumption"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.phase_one_consumption

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.phase_one_consumption


class PhaseOneFeed(SensorBase):
    """Phase One Feed Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Phase One Feed object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Phase 1 Feed"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.phase_one_feed

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.phase_one_feed


class PhaseTwoConsumption(SensorBase):
    """Phase Two Consumption Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Phase Two Consumption object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Phase 2 Consumption"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.phase_two_consumption

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.phase_two_consumption


class PhaseTwoFeed(SensorBase):
    """Phase Two Feed Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Phase One Feed object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Phase 2 Feed"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.phase_two_feed

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.phase_two_feed


class PhaseThreeConsumption(SensorBase):
    """Phase Three Consumption Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Phase Three Consumption object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Phase 3 Consumption"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.phase_three_consumption

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.phase_three_consumption


class PhaseThreeFeed(SensorBase):
    """Phase Three Feed Sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, sma: SMA, device: DeviceInfo
    ) -> None:
        """Init the Phase Three Feed object.

        @param coordinator:
        @param sma: SMA API object
        @param device:
        """
        self._attr_name = f"{sma.name} Phase 3 Feed"

        super().__init__(coordinator, sma, device)

        self._state = self._sma.phase_three_feed

    @property
    def native_value(self) -> float:
        """Native value of the sensor."""
        return self._sma.phase_three_feed
