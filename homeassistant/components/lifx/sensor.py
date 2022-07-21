"""Sensor entities for LIFX integration."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_MINUTES
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_RSSI,
    DOMAIN,
    HEV_CYCLE_DURATION,
    HEV_CYCLE_LAST_POWER,
    HEV_CYCLE_LAST_RESULT,
    HEV_CYCLE_REMAINING,
)
from .coordinator import LIFXUpdateCoordinator
from .util import lifx_features

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

RSSI_SENSOR = SensorEntityDescription(
    key=ATTR_RSSI,
    name="RSSI",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class=SensorStateClass.MEASUREMENT,
    device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    entity_registry_enabled_default=False,
)

HEV_SENSORS = [
    SensorEntityDescription(
        key=HEV_CYCLE_DURATION,
        name="Clean Cycle Duration",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key=HEV_CYCLE_REMAINING,
        name="Clean Cycle Remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=TIME_MINUTES,
    ),
    SensorEntityDescription(
        key=HEV_CYCLE_LAST_POWER,
        name="Clean Cycle Last Power",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=HEV_CYCLE_LAST_RESULT,
        name="Clean Cycle Last Result",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up LIFX from a config entry."""
    domain_data = hass.data[DOMAIN]
    coordinator: LIFXUpdateCoordinator = domain_data[entry.entry_id]
    sensors: list[LifxSensorEntity] = [
        LifxRssiSensorEntity(coordinator=coordinator, description=RSSI_SENSOR)
    ]

    if lifx_features(coordinator.device)["hev"]:
        for sensor_description in HEV_SENSORS:
            sensors.append(
                LifxHevSensorEntity(
                    coordinator=coordinator, description=sensor_description
                )
            )

    async_add_entities(sensors, update_before_add=True)


class LifxSensorEntity(CoordinatorEntity[LIFXUpdateCoordinator], SensorEntity):
    """LIFX sensor entity base class."""

    _attr_has_entity_name: bool = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator

        self.entity_description = description
        self._attr_unique_id = (
            f"{self.coordinator.serial_number}_{self.entity_description.key}"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.coordinator.mac_address)},
            manufacturer="LIFX",
            name=self.coordinator.label,
        )
        self._async_update_attrs()

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the sensor native value."""
        return self._attr_native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    @abstractmethod
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""


class LifxRssiSensorEntity(LifxSensorEntity):
    """LIFX RSSI Sensor."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise a LIFX RSSI sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._attr_name = description.name

    @property
    def native_unit_of_measurement(self) -> str:
        """Get the RSSI unit of measurement."""
        return str(self.coordinator.get_rssi_unit_of_measurement())

    @callback
    def _async_update_attrs(self) -> None:
        """Handle attribute updates."""
        self._attr_native_value = self.coordinator.rssi

    @callback
    async def async_added_to_hass(self) -> None:
        """Enable fetch of RSSI data."""
        self.coordinator.fetch_rssi = True
        await super().async_added_to_hass()

    @callback
    async def async_will_remove_from_hass(self) -> None:
        """Disable fetching RSSI data."""
        self.coordinator.fetch_rssi = False
        await super().async_will_remove_from_hass()


class LifxHevSensorEntity(LifxSensorEntity):
    """LIFX HEV Sensor."""

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise a LIFX HEV sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._attr_name = description.name
        self.coordinator.update_method = cast(
            Callable, f"self.coordinator._async_fetch_{self.entity_description.key}"
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_native_value = getattr(
            self.coordinator, self.entity_description.key, None
        )

    @callback
    async def async_added_to_hass(self) -> None:
        """Enable fetch of HEV data."""
        setattr(self.coordinator, f"fetch_{self.entity_description.key}", True)
        await super().async_added_to_hass()

    @callback
    async def async_will_remove_from_hass(self) -> None:
        """Disable fetching HEV data."""
        setattr(self.coordinator, f"fetch_{self.entity_description.key}", False)
        await super().async_will_remove_from_hass()
