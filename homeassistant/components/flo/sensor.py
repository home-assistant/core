"""Support for Flo Water Monitor sensors."""

from typing import List, Optional

from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_PSI,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    VOLUME_GALLONS,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.temperature import fahrenheit_to_celsius

from .const import DOMAIN as FLO_DOMAIN, SIGNAL_WATER_CONSUMPTION_UPDATED
from .device import FloDevice
from .entity import FloEntity

DEPENDENCIES = ["flo"]

WATER_ICON = "mdi:water"
GAUGE_ICON = "mdi:gauge"
NAME_DAILY_USAGE = "Today's Water Usage"
NAME_CURRENT_SYSTEM_MODE = "Current System Mode"
NAME_FLOW_RATE = "Water Flow Rate"
NAME_TEMPERATURE = "Water Temperature"
NAME_WATER_PRESSURE = "Water Pressure"
NAME_WIFI_SIGNAL_STRENGTH = "WiFi Signal Strength"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo sensors from config entry."""
    devices: List[FloDevice] = hass.data[FLO_DOMAIN]["devices"]
    entities = []
    entities.extend([FloDailyUsageSensor(device) for device in devices])
    entities.extend([FloSystemModeSensor(device) for device in devices])
    entities.extend([FloCurrentFlowRateSensor(device) for device in devices])
    entities.extend([FloTemperatureSensor(device) for device in devices])
    entities.extend([FloPressureSensor(device) for device in devices])
    entities.extend([FloWifiStrengthSensor(device) for device in devices])
    async_add_entities(entities, True)


class FloDailyUsageSensor(FloEntity):
    """Monitors the daily water usage."""

    def __init__(self, device):
        """Initialize the daily water usage sensor."""
        super().__init__(
            f"{device.mac_address}_daily_consumption", NAME_DAILY_USAGE, device
        )
        self._state: float = None

    @property
    def icon(self) -> str:
        """Return the daily usage icon."""
        return WATER_ICON

    @property
    def state(self) -> Optional[float]:
        """Return the current daily usage."""
        if self._device.consumption_today is None:
            return None
        return round(self._device.consumption_today, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return VOLUME_GALLONS

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._device.mac_address}-{SIGNAL_WATER_CONSUMPTION_UPDATED}",
                self.async_write_ha_state,
            )
        )


class FloSystemModeSensor(FloEntity):
    """Monitors the current Flo system mode."""

    def __init__(self, device):
        """Initialize the system mode sensor."""
        super().__init__(
            f"{device.mac_address}_current_system_mode",
            NAME_CURRENT_SYSTEM_MODE,
            device,
        )
        self._state: str = None

    @property
    def state(self) -> Optional[str]:
        """Return the current system mode."""
        if not self._device.current_system_mode:
            return STATE_UNKNOWN
        return self._device.current_system_mode


class FloCurrentFlowRateSensor(FloEntity):
    """Monitors the current water flow rate."""

    def __init__(self, device):
        """Initialize the flow rate sensor."""
        super().__init__(
            f"{device.mac_address}_current_flow_rate", NAME_FLOW_RATE, device
        )
        self._state: float = None

    @property
    def icon(self) -> str:
        """Return the daily usage icon."""
        return GAUGE_ICON

    @property
    def state(self) -> Optional[float]:
        """Return the current flow rate."""
        if self._device.current_flow_rate is None:
            return None
        return round(self._device.current_flow_rate, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return "gpm"


class FloTemperatureSensor(FloEntity):
    """Monitors the temperature."""

    def __init__(self, device):
        """Initialize the temperature sensor."""
        super().__init__(f"{device.mac_address}_temperature", NAME_TEMPERATURE, device)
        self._state: float = None

    @property
    def state(self) -> Optional[float]:
        """Return the current temperature."""
        if self._device.temperature is None:
            return None
        return round(fahrenheit_to_celsius(self._device.temperature), 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return TEMP_CELSIUS

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_TEMPERATURE


class FloPressureSensor(FloEntity):
    """Monitors the water pressure."""

    def __init__(self, device):
        """Initialize the pressure sensor."""
        super().__init__(
            f"{device.mac_address}_water_pressure", NAME_WATER_PRESSURE, device
        )
        self._state: float = None

    @property
    def state(self) -> Optional[float]:
        """Return the current water pressure."""
        if self._device.current_psi is None:
            return None
        return round(self._device.current_psi, 1)

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return PRESSURE_PSI

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_PRESSURE


class FloWifiStrengthSensor(FloEntity):
    """Monitors the wifi signal."""

    def __init__(self, device):
        """Initialize the wifi signal sensor."""
        super().__init__(
            f"{device.mac_address}_wifi_signal_strength",
            NAME_WIFI_SIGNAL_STRENGTH,
            device,
        )
        self._state: int = None

    @property
    def state(self) -> Optional[int]:
        """Return the current water pressure."""
        if self._device.rssi is None:
            return None
        return self._device.rssi

    @property
    def unit_of_measurement(self) -> str:
        """Return gallons as the unit measurement for water."""
        return "rssi"

    @property
    def device_class(self) -> Optional[str]:
        """Return the device class for this sensor."""
        return DEVICE_CLASS_SIGNAL_STRENGTH
