"""Support for BSB-Lan sensors."""

from __future__ import annotations

from bsblan import BSBLAN, Device, Info, Sensor, StaticState

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    DEGREE,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HomeAssistantBSBLANData
from .const import DOMAIN
from .coordinator import BSBLanUpdateCoordinator


def get_unit_of_measurement(unit: str) -> str | None:
    """Map BSBLAN units to Home Assistant units."""
    if unit in ("°C", "&deg;C"):
        return UnitOfTemperature.CELSIUS
    if unit in ("°F", "&deg;F"):
        return UnitOfTemperature.FAHRENHEIT
    if unit == "bar":
        return UnitOfPressure.BAR
    if unit == "%":
        return PERCENTAGE
    if unit == "°":
        return DEGREE
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BSBLAN sensor based on a config entry."""
    data: HomeAssistantBSBLANData = hass.data[DOMAIN][entry.entry_id]

    sensor_data: Sensor = data.coordinator.data["sensor"]
    entities = []

    for attr_name in dir(sensor_data):
        if attr_name.startswith("_"):
            continue  # Skip private attributes

        attr_value = getattr(sensor_data, attr_name)
        if hasattr(attr_value, "value") and hasattr(attr_value, "unit"):
            unit = get_unit_of_measurement(attr_value.unit)
            entities.append(
                BSBLANSensor(
                    coordinator=data.coordinator,
                    client=data.client,
                    device=data.device,
                    info=data.info,
                    static=data.static,
                    entry=entry,
                    key=attr_name,
                    name=attr_name.replace("_", " ").title(),
                    unit=unit,
                )
            )

    async_add_entities(entities)


class BSBLANSensor(CoordinatorEntity[BSBLanUpdateCoordinator], SensorEntity):
    """Defines a BSBLAN sensor."""

    def __init__(
        self,
        coordinator: BSBLanUpdateCoordinator,
        client: BSBLAN,
        device: Device,
        info: Info,
        static: StaticState,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str | None,
    ) -> None:
        """Initialize BSBLAN sensor."""
        super().__init__(coordinator)

        self.client = client
        self.key = key
        self._attr_name = f"{device.name} {name}"
        self._attr_unique_id = f"{format_mac(device.MAC)}-{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, format_mac(device.MAC))},
            name=device.name,
            manufacturer="BSBLAN Inc.",
            model=info.device_identification.value,
            sw_version=f"{device.version}",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        sensor_data: Sensor = self.coordinator.data["sensor"]
        attr_value = getattr(sensor_data, self.key, None)
        if attr_value is None or not hasattr(attr_value, "value"):
            return None
        return attr_value.value

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        if self.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            return SensorDeviceClass.TEMPERATURE
        if self.native_unit_of_measurement == UnitOfPressure.BAR:
            return SensorDeviceClass.PRESSURE
        if self.native_unit_of_measurement == PERCENTAGE:
            return SensorDeviceClass.POWER_FACTOR
        return None

    @property
    def state_class(self) -> SensorStateClass:
        """Return the state class of the sensor."""
        return SensorStateClass.MEASUREMENT
