"""The sensor entity for the Youless integration."""
from datetime import timedelta
from typing import Any, Dict, Optional

from youless_api import YoulessAPI
from youless_api.youless_sensor import YoulessSensor

from homeassistant import core
from homeassistant.components.youless import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, DEVICE_CLASS_POWER
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType
from homeassistant.util import Throttle


async def async_setup_entry(
    hass: core.HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Initialize the integration."""
    gateway = hass.data[DOMAIN][entry.entry_id]
    device = entry.data[CONF_DEVICE]
    sensors = [
        GasSensor(gateway, device),
        PowerMeterSensor(gateway, device, "low"),
        PowerMeterSensor(gateway, device, "high"),
        PowerMeterSensor(gateway, device, "total"),
        CurrentPowerSensor(gateway, device),
        DeliveryMeterSensor(gateway, device, "total"),
        DeliveryMeterSensor(gateway, device, "current"),
    ]

    async_add_entities(sensors)


class YoulessBaseSensor(Entity):
    """The base sensor for Youless."""

    def __init__(
        self, gateway: YoulessAPI, device: str, friendly_name: str, sensor_id: str
    ):
        """Create the sensor."""
        self._gateway = gateway
        self._friendly_name = friendly_name
        self._device = device
        self._sensor_id = sensor_id

    @Throttle(timedelta(seconds=30))
    def update(self) -> None:
        """Update the gateway value."""
        self._gateway.update()

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
            "identifiers": {(DOMAIN, self._gateway.mac_address)},
            "name": self._device,
            "manufacturer": "YouLess",
            "model": self._gateway.model,
        }


class GasSensor(YoulessBaseSensor):
    """The Youless gas sensor."""

    def __init__(self, gateway: YoulessAPI, device: str):
        """Instantiate a gas sensor."""
        super().__init__(gateway, device, "Gas meter", "gas")

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return f"{self._device} gas"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return "mdi:fire"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        return self._gateway.gas_meter


class CurrentPowerSensor(YoulessBaseSensor):
    """The current power usage sensor."""

    def __init__(self, gateway: YoulessAPI, device: str):
        """Instantiate the usage meter."""
        super().__init__(gateway, device, "Power usage", "usage")
        self._device = device

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return f"{self._device} ssage"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        return self._gateway.current_power_usage

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_POWER

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return "mdi:power-socket"


class DeliveryMeterSensor(YoulessBaseSensor):
    """The Youless delivery meter value sensor."""

    def __init__(self, gateway: YoulessAPI, device: str, dev_type: str):
        """Instantiate a delivery meter sensor."""
        super().__init__(
            gateway, device, f"Delivery meter {dev_type}", f"delivery_{dev_type}"
        )
        self._type = dev_type

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return f"{self._device} delivery {self._type}"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return "mdi:counter"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        if self._gateway.delivery_meter is None:
            return None

        return getattr(self._gateway.delivery_meter, f"_{self._type}", None)

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_POWER


class PowerMeterSensor(YoulessBaseSensor):
    """The Youless low meter value sensor."""

    def __init__(self, gateway: YoulessAPI, device: str, dev_type: str):
        """Instantiate a power meter sensor."""
        super().__init__(
            gateway, device, f"Power meter {dev_type}", f"power_{dev_type}"
        )
        self._device = device
        self._type = dev_type

    @property
    def name(self) -> Optional[str]:
        """Return the name of the meter."""
        return f"{self._device} power {self._type}"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        return "mdi:counter"

    @property
    def get_sensor(self) -> Optional[YoulessSensor]:
        """Get the sensor for providing the value."""
        if self._gateway.power_meter is None:
            return None

        return getattr(self._gateway.power_meter, f"_{self._type}", None)

    @property
    def device_class(self) -> Optional[str]:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_POWER
