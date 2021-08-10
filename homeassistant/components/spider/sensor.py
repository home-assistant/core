"""Support for Spider Powerplugs (energy & power)."""
from datetime import datetime

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(hass, config, async_add_entities):
    """Initialize a Spider Power Plug."""
    api = hass.data[DOMAIN][config.entry_id]
    entities = []

    for entity in await hass.async_add_executor_job(api.get_power_plugs):
        entities.append(SpiderPowerPlugEnergy(api, entity))
        entities.append(SpiderPowerPlugPower(api, entity))

    async_add_entities(entities)


class SpiderPowerPlugEnergy(SensorEntity):
    """Representation of a Spider Power Plug (energy)."""

    _attr_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, api, power_plug) -> None:
        """Initialize the Spider Power Plug."""
        self.api = api
        self.power_plug = power_plug

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.power_plug.id)},
            "name": self.power_plug.name,
            "manufacturer": self.power_plug.manufacturer,
            "model": self.power_plug.model,
        }

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self.power_plug.id}_total_energy_today"

    @property
    def name(self) -> str:
        """Return the name of the sensor if any."""
        return f"{self.power_plug.name} Total Energy Today"

    @property
    def state(self) -> float:
        """Return todays energy usage in Kwh."""
        return round(self.power_plug.today_energy_consumption / 1000, 2)

    @property
    def last_reset(self) -> datetime:
        """Return the time when last reset; Every midnight."""
        return dt_util.as_utc(
            dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )

    def update(self) -> None:
        """Get the latest data."""
        self.power_plug = self.api.get_power_plug(self.power_plug.id)


class SpiderPowerPlugPower(SensorEntity):
    """Representation of a Spider Power Plug (power)."""

    _attr_device_class = DEVICE_CLASS_POWER
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_unit_of_measurement = POWER_WATT

    def __init__(self, api, power_plug) -> None:
        """Initialize the Spider Power Plug."""
        self.api = api
        self.power_plug = power_plug

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.power_plug.id)},
            "name": self.power_plug.name,
            "manufacturer": self.power_plug.manufacturer,
            "model": self.power_plug.model,
        }

    @property
    def unique_id(self) -> str:
        """Return the ID of this sensor."""
        return f"{self.power_plug.id}_power_consumption"

    @property
    def name(self) -> str:
        """Return the name of the sensor if any."""
        return f"{self.power_plug.name} Power Consumption"

    @property
    def state(self) -> float:
        """Return the current power usage in W."""
        return round(self.power_plug.current_energy_consumption)

    def update(self) -> None:
        """Get the latest data."""
        self.power_plug = self.api.get_power_plug(self.power_plug.id)
