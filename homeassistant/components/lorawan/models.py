"""Defines models used by the library."""
import datetime

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature


class Device:
    """Holds a LoRaWAN device representation."""

    def __init__(self, device_eui: str, name: str) -> None:
        """Construct the Device object.

        :param device_eui: LoRaWAN IEEE-64 Extended Unique Identifier, as hex string
        :param name: Device name
        """
        self._device_eui = device_eui.upper()
        self._name = name

    @property
    def device_eui(self) -> str:
        """LoRaWAN IEEE-64 Extended Unique Identifier, as hex string."""
        return self._device_eui

    @property
    def name(self) -> str:
        """Device name."""
        return self._name


class SensorTypes:
    """Collection of sensor entities defining measurements of a device."""

    class SensorType:
        """Base entity type."""

        DATA_KEY: str
        UNIT: str
        DEVICE_CLASS: SensorDeviceClass
        NAME: str

    class BatteryLevel(SensorType):
        """Battery entity type."""

        DATA_KEY = "battery_level"
        UNIT = UnitOfElectricPotential.VOLT
        DEVICE_CLASS = SensorDeviceClass.VOLTAGE
        NAME = "Battery level"

    class Temperature(SensorType):
        """Temperature entity type."""

        DATA_KEY = "temperature"
        UNIT = UnitOfTemperature.CELSIUS
        DEVICE_CLASS = SensorDeviceClass.TEMPERATURE
        NAME = "Temperature"


class Sensors:
    """Holds parsed sensor values."""

    @property
    def battery(self) -> float:
        """Remaining battery, in %."""
        return self._battery

    @battery.setter
    def battery(self, value: int | float) -> None:
        value = float(value)
        if value < 0.0 or value > 100.0:
            raise ValueError(f'Battery value must be in [0:100] not "{value}"')
        self._battery = value

    @property
    def battery_level(self) -> float:
        """Battery level, in Volts."""
        return self._battery_level

    @battery_level.setter
    def battery_level(self, value: int | float) -> None:
        value = float(value)
        if value < 0.0:
            raise ValueError(f'Battery level must be positive not "{value}"')
        self._battery_level = value

    @property
    def pir_status(self) -> bool:
        """Infrared presence detection."""
        return self._pir_status

    @pir_status.setter
    def pir_status(self, value: bool) -> None:
        self._pir_status = value

    @property
    def temperature(self) -> float:
        """Temperature in °C."""
        return self._temperature

    @temperature.setter
    def temperature(self, value: float) -> None:
        self._temperature = value

    @property
    def time_since_last_event(self) -> int:
        """Elapsed time since last event.

        :return: Time in seconds
        """
        return self._time_since_last_event

    @time_since_last_event.setter
    def time_since_last_event(self, value: datetime.timedelta | int) -> None:
        """Elapsed time since last event.

        :param value: Time in seconds or datetime.timedelta()
        """
        if isinstance(value, datetime.timedelta):
            value = int(value.total_seconds())
        self._time_since_last_event = value

    @property
    def total_event_counter(self) -> int:
        """Number of events that occurred in the past."""
        return self._total_event_counter

    @total_event_counter.setter
    def total_event_counter(self, value: int) -> None:
        self._total_event_counter = value


class Uplink:
    """Generic uplink class to hold parsed data."""

    def __init__(self, payload: bytes, f_port: int) -> None:
        """Construct the Uplink object.

        :param payload: Uplink payload in bytes
        :param f_port: LoRaWAN frame port
        """
        self._payload = payload
        self._f_port = f_port

        self.sensors = Sensors()

    @property
    def payload(self) -> bytes:
        """Uplink payload in bytes."""
        return self._payload

    @property
    def f_port(self) -> int:
        """LoRaWAN FPort bytes."""
        return self._f_port
