"""Support for Anova Sous Vide Sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from anova_wifi import AnovaOffline, AnovaPrecisionCooker, AnovaPrecisionCookerSensor
import async_timeout

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import ANOVA_CLIENT, ANOVA_FIRMWARE_VERSION, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    AnovaPrecisionCookerSensor.COOK_TIME: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        name="Cook Time",
    ),
    AnovaPrecisionCookerSensor.STATE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.STATE, name="State"
    ),
    AnovaPrecisionCookerSensor.MODE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.MODE, name="Mode"
    ),
    AnovaPrecisionCookerSensor.TARGET_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Target Temperature",
    ),
    AnovaPrecisionCookerSensor.COOK_TIME_REMAINING: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        name="Cook Time Remaining",
    ),
    AnovaPrecisionCookerSensor.HEATER_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.HEATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Heater Temperature",
    ),
    AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Triac Temperature",
    ),
    AnovaPrecisionCookerSensor.WATER_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.WATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Water Temperature",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova Sous Vide device."""
    anova_wifi = hass.data[DOMAIN][entry.entry_id][ANOVA_CLIENT]
    firmware_version = hass.data[DOMAIN][entry.entry_id][ANOVA_FIRMWARE_VERSION]
    coordinator = AnovaCoordinator(hass, anova_wifi, firmware_version)
    await coordinator.async_config_entry_first_refresh()
    sensors = [
        AnovaEntity(coordinator, description, sensor)
        for sensor, description in SENSOR_DESCRIPTIONS.items()
    ]
    async_add_entities(sensors)


class AnovaCoordinator(DataUpdateCoordinator):
    """Anova custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        anova_api: AnovaPrecisionCooker,
        firmware_version: str,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            name="Anova Precision Cooker",
            logger=_LOGGER,
            update_interval=timedelta(seconds=30),
        )
        if self.config_entry is not None:
            self._device_id = self.config_entry.data["device_id"]
            self.device_info = DeviceInfo(
                identifiers={((DOMAIN), self._device_id)},
                name="Anova Precision Cooker",
                manufacturer="Anova",
                model="Precision Cooker",
                sw_version=firmware_version,
            )
        else:
            _LOGGER.error("Anova Coordinator was setup without config entry")

        self.anova_api = anova_api

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                return await self.anova_api.update(self._device_id)
        except AnovaOffline as err:
            raise UpdateFailed(err) from err


class AnovaEntity(CoordinatorEntity, SensorEntity):
    """An entity using CoordinatorEntity."""

    def __init__(
        self,
        coordinator: AnovaCoordinator,
        description: SensorEntityDescription,
        sensor_update_key: str,
    ) -> None:
        """Set up an Anova Sensor Entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_update_key = sensor_update_key
        self._sensor_data = None
        self._attr_unique_id = (
            f"Anova_{coordinator._device_id}_{description.key}".lower()
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self._sensor_data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = self.coordinator.data["sensors"][self._sensor_update_key]
        self.async_write_ha_state()
