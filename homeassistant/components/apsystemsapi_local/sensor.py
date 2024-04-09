"""The read-only sensors for APsystems local API integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from APsystemsEZ1 import ReturnOutputData
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApSystemsDataCoordinator

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default="solar"): cv.string,
    }
)


@dataclass(frozen=True, kw_only=True)
class ApsystemsLocalApiSensorDescription(SensorEntityDescription):
    """Describes AdGuard Home sensor entity."""

    value_fn: Callable[[ReturnOutputData], float | None]


SENSORS: tuple[ApsystemsLocalApiSensorDescription, ...] = (
    ApsystemsLocalApiSensorDescription(
        key="total_power",
        translation_key="total_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.p1 + c.p2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="total_power_p1",
        translation_key="total_power_p1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.p1,
    ),
    ApsystemsLocalApiSensorDescription(
        key="total_power_p2",
        translation_key="total_power_p2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.p2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="lifetime_production",
        translation_key="lifetime_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda c: c.te1 + c.te2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="lifetime_production_p1",
        translation_key="lifetime_production_p1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda c: c.te1,
    ),
    ApsystemsLocalApiSensorDescription(
        key="lifetime_production_p2",
        translation_key="lifetime_production_p2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda c: c.te2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="today_production",
        translation_key="today_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e1 + c.e2,
    ),
    ApsystemsLocalApiSensorDescription(
        key="today_production_p1",
        translation_key="today_production_p1",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e1,
    ),
    ApsystemsLocalApiSensorDescription(
        key="today_production_p2",
        translation_key="today_production_p2",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.e2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = config["COORDINATOR"]
    device_name = config[CONF_NAME]

    add_entities(
        ApSystemsSensorWithDescription(coordinator, desc, device_name)
        for desc in SENSORS
    )


class ApSystemsSensorWithDescription(CoordinatorEntity, SensorEntity):
    """Base sensor to be used with description."""

    entity_description: ApsystemsLocalApiSensorDescription

    def __init__(
        self,
        coordinator: ApSystemsDataCoordinator,
        entity_description: ApsystemsLocalApiSensorDescription,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state: int | float | None = None
        self.entity_description = entity_description
        self._device_name = device_name
        self._attr_unique_id = f"apsystemsapi_{device_name}_{entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Get the DeviceInfo."""
        return DeviceInfo(
            identifiers={("apsystemsapi_local", self._device_name)},
            name=self._device_name,
            manufacturer="APsystems",
            model="EZ1-M",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data is not None:
            self._state = self.entity_description.value_fn(self.coordinator.data)
        self.async_write_ha_state()

    @property  # type: ignore[misc]
    def state(self) -> float | None:
        """Return the state of the sensor."""
        return self._state
