"""Support for Spider Powerplugs (energy & power)."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize a Spider Power Plug."""
    api = hass.data[DOMAIN][config.entry_id]
    entities: list[SensorEntity] = []

    for entity in await hass.async_add_executor_job(api.get_power_plugs):
        entities.append(SpiderPowerPlugEnergy(api, entity))
        entities.append(SpiderPowerPlugPower(api, entity))

    async_add_entities(entities)


class SpiderPowerPlugEnergy(SensorEntity):
    """Representation of a Spider Power Plug (energy)."""

    _attr_has_entity_name = True
    _attr_translation_key = "total_energy_today"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, api, power_plug) -> None:
        """Initialize the Spider Power Plug."""
        self.api = api
        self.power_plug = power_plug

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.power_plug.id)},
            manufacturer=self.power_plug.manufacturer,
            model=self.power_plug.model,
            name=self.power_plug.name,
        )

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self.power_plug.id}_total_energy_today"

    @property
    def native_value(self) -> float:
        """Return todays energy usage in Kwh."""
        return round(self.power_plug.today_energy_consumption / 1000, 2)

    def update(self) -> None:
        """Get the latest data."""
        self.power_plug = self.api.get_power_plug(self.power_plug.id)


class SpiderPowerPlugPower(SensorEntity):
    """Representation of a Spider Power Plug (power)."""

    _attr_has_entity_name = True
    _attr_translation_key = "power_consumption"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, api, power_plug) -> None:
        """Initialize the Spider Power Plug."""
        self.api = api
        self.power_plug = power_plug

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.power_plug.id)},
            manufacturer=self.power_plug.manufacturer,
            model=self.power_plug.model,
            name=self.power_plug.name,
        )

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self.power_plug.id}_power_consumption"

    @property
    def native_value(self) -> float:
        """Return the current power usage in W."""
        return round(self.power_plug.current_energy_consumption)

    def update(self) -> None:
        """Get the latest data."""
        self.power_plug = self.api.get_power_plug(self.power_plug.id)
