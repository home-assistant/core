"""Demo platform that has a couple of fake sensors."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from . import DOMAIN


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo sensors."""
    async_add_entities(
        [
            DemoSensor(
                "sensor_1",
                "Outside Temperature",
                15.6,
                SensorDeviceClass.TEMPERATURE,
                SensorStateClass.MEASUREMENT,
                UnitOfTemperature.CELSIUS,
                12,
            ),
            DemoSensor(
                "sensor_2",
                "Outside Humidity",
                54,
                SensorDeviceClass.HUMIDITY,
                SensorStateClass.MEASUREMENT,
                PERCENTAGE,
                None,
            ),
            DemoSensor(
                "sensor_3",
                "Carbon monoxide",
                54,
                SensorDeviceClass.CO,
                SensorStateClass.MEASUREMENT,
                CONCENTRATION_PARTS_PER_MILLION,
                None,
            ),
            DemoSensor(
                "sensor_4",
                "Carbon dioxide",
                54,
                SensorDeviceClass.CO2,
                SensorStateClass.MEASUREMENT,
                CONCENTRATION_PARTS_PER_MILLION,
                14,
            ),
            DemoSensor(
                "sensor_5",
                "Power consumption",
                100,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT,
                UnitOfPower.WATT,
                None,
            ),
            DemoSumSensor(
                "sensor_6",
                "Total energy 1",
                0.5,  # 6kWh / h
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
                UnitOfEnergy.KILO_WATT_HOUR,
                None,
                "total_energy_kwh",
            ),
            DemoSumSensor(
                "sensor_7",
                "Total energy 2",
                0.00025,  # 0.003 MWh/h (3 kWh / h)
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL,
                UnitOfEnergy.MEGA_WATT_HOUR,
                None,
                "total_energy_mwh",
            ),
            DemoSumSensor(
                "sensor_8",
                "Total gas 1",
                0.025,  # 0.30 m³/h (10.6 ft³ / h)
                SensorDeviceClass.GAS,
                SensorStateClass.TOTAL,
                UnitOfVolume.CUBIC_METERS,
                None,
                "total_gas_m3",
            ),
            DemoSumSensor(
                "sensor_9",
                "Total gas 2",
                1.0,  # 12 ft³/h (0.34 m³ / h)
                SensorDeviceClass.GAS,
                SensorStateClass.TOTAL,
                UnitOfVolume.CUBIC_FEET,
                None,
                "total_gas_ft3",
            ),
            DemoSensor(
                unique_id="sensor_10",
                name="Thermostat mode",
                state="eco",
                device_class=SensorDeviceClass.ENUM,
                state_class=None,
                unit_of_measurement=None,
                battery=None,
                options=["away", "comfort", "eco", "sleep"],
                translation_key="thermostat_mode",
            ),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoSensor(SensorEntity):
    """Representation of a Demo sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: StateType,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass | None,
        unit_of_measurement: str | None,
        battery: StateType,
        options: list[str] | None = None,
        translation_key: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_native_value = state
        self._attr_state_class = state_class
        self._attr_unique_id = unique_id
        self._attr_options = options
        self._attr_translation_key = translation_key

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

        if battery:
            self._attr_extra_state_attributes = {ATTR_BATTERY_LEVEL: battery}


class DemoSumSensor(RestoreSensor):
    """Representation of a Demo sensor."""

    _attr_should_poll = False
    _attr_native_value: float

    def __init__(
        self,
        unique_id: str,
        name: str,
        five_minute_increase: float,
        device_class: SensorDeviceClass,
        state_class: SensorStateClass | None,
        unit_of_measurement: str | None,
        battery: StateType,
        suggested_entity_id: str,
    ) -> None:
        """Initialize the sensor."""
        self.entity_id = f"{SENSOR_DOMAIN}.{suggested_entity_id}"
        self._attr_device_class = device_class
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_native_value = 0
        self._attr_state_class = state_class
        self._attr_unique_id = unique_id
        self._five_minute_increase = five_minute_increase

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

        if battery:
            self._attr_extra_state_attributes = {ATTR_BATTERY_LEVEL: battery}

    @callback
    def _async_bump_sum(self, now: datetime) -> None:
        """Bump the sum."""
        self._attr_native_value += self._five_minute_increase
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = cast(float, state.native_value)

        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_bump_sum, timedelta(minutes=5)
            ),
        )
