"""The sensor entity for the Youless integration."""
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from youless_api.youless_sensor import YoulessSensor

from homeassistant import core
from homeassistant.components.youless import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, DEVICE_CLASS_POWER
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Initialize the integration."""
    gateway = hass.data[DOMAIN][entry.entry_id]
    device = entry.data[CONF_DEVICE]

    async def async_update_data():
        """Fetch data from the API."""
        await hass.async_add_executor_job(gateway.update)
        return gateway

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="youless_gateway",
        update_method=async_update_data,
        update_interval=timedelta(seconds=2),
    )

    await coordinator.async_request_refresh()

    async_add_entities(
        [
            GasSensor(coordinator, device),
            PowerMeterSensor(coordinator, device, "low"),
            PowerMeterSensor(coordinator, device, "high"),
            PowerMeterSensor(coordinator, device, "total"),
            CurrentPowerSensor(coordinator, device),
            DeliveryMeterSensor(coordinator, device, "low"),
            DeliveryMeterSensor(coordinator, device, "high"),
        ]
    )


class YoulessBaseSensor(CoordinatorEntity, Entity):
    """The base sensor for Youless."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: str,
        device_group: str,
        friendly_name: str,
        sensor_id: str,
    ):
        """Create the sensor."""
        super().__init__(coordinator)
        self._friendly_name = friendly_name
        self._device = device
        self._device_group = device_group
        self._sensor_id = sensor_id

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Property to get the underlying sensor object."""
        return None

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement for the sensor."""
        if self.get_sensor is None:
            return None

        return self.get_sensor.unit_of_measurement

    @property
    def state(self) -> StateType:
        """Determine the state value, only if a sensor is initialized."""
        if self.get_sensor is None:
            return None

        return self.get_sensor.value

    @property
    def unique_id(self) -> Optional[str]:
        """Return the uniquely generated id."""
        return f"{DOMAIN}_{self._device}_{self._sensor_id}"

    @property
    def available(self) -> bool:
        """Return a flag to indicate the sensor not being available."""
        return self.get_sensor is not None

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._device, self._device_group)},
            "name": self._friendly_name,
            "manufacturer": "YouLess",
            "model": self.coordinator.data.model,
        }


class GasSensor(YoulessBaseSensor):
    """The Youless gas sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: str):
        """Instantiate a gas sensor."""
        super().__init__(coordinator, device, "gas", "Gas meter", "gas")

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return "Gas usage"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return "mdi:fire"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        return self.coordinator.data.gas_meter


class CurrentPowerSensor(YoulessBaseSensor):
    """The current power usage sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: str):
        """Instantiate the usage meter."""
        super().__init__(coordinator, device, "power", "Power usage", "usage")
        self._device = device

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return "Power Usage"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        return self.coordinator.data.current_power_usage

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_POWER


class DeliveryMeterSensor(YoulessBaseSensor):
    """The Youless delivery meter value sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: str, dev_type: str):
        """Instantiate a delivery meter sensor."""
        super().__init__(
            coordinator, device, "delivery", "Power delivery", f"delivery_{dev_type}"
        )
        self._type = dev_type

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return f"Power delivery {self._type}"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        if self.coordinator.data.delivery_meter is None:
            return None

        return getattr(self.coordinator.data.delivery_meter, f"_{self._type}", None)

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_POWER


class PowerMeterSensor(YoulessBaseSensor):
    """The Youless low meter value sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, device: str, dev_type: str):
        """Instantiate a power meter sensor."""
        super().__init__(
            coordinator, device, "power", "Power usage", f"power_{dev_type}"
        )
        self._device = device
        self._type = dev_type

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return f"Power {self._type}"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        if self.coordinator.data.power_meter is None:
            return None

        return getattr(self.coordinator.data.power_meter, f"_{self._type}", None)

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_POWER
