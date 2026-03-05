"""
Domain models for the PajGPS integration.

This module contains pure data classes representing PajGPS entities.
These classes have no dependencies on HTTP, API logic, or Home Assistant internals.
"""
import logging

_LOGGER = logging.getLogger(__name__)


class PajGPSDevice:
    """Representation of single Paj GPS device."""

    # Basic attributes
    id: int
    name: str
    imei: str
    model: str
    has_battery: bool

    # Alarms
    has_alarm_sos: bool
    alarm_sos_enabled: bool
    has_alarm_shock: bool
    alarm_shock_enabled: bool
    has_alarm_voltage: bool
    alarm_voltage_enabled: bool
    has_alarm_battery: bool
    alarm_battery_enabled: bool
    has_alarm_speed: bool
    alarm_speed_enabled: bool
    has_alarm_power_cutoff: bool
    alarm_power_cutoff_enabled: bool
    has_alarm_ignition: bool
    alarm_ignition_enabled: bool
    has_alarm_drop: bool
    alarm_drop_enabled: bool

    def __init__(self, id: int) -> None:
        """Initialize the PajGPSDevice class."""
        self.id = id

    def is_alert_enabled(self, _alert_type) -> bool:
        """Check if the alert is available and enabled for the device."""
        if _alert_type == 1:                 # Shock Alert
            return self.has_alarm_shock and self.alarm_shock_enabled
        elif _alert_type == 2:               # Battery Alert
            return self.has_alarm_battery and self.alarm_battery_enabled
        elif _alert_type == 4:               # SOS Alert
            return self.has_alarm_sos and self.alarm_sos_enabled
        elif _alert_type == 5:               # Speed Alert
            return self.has_alarm_speed and self.alarm_speed_enabled
        elif _alert_type == 6:               # Power Cutoff Alert
            return self.has_alarm_power_cutoff and self.alarm_power_cutoff_enabled
        elif _alert_type == 7:               # Ignition Alert
            return self.has_alarm_ignition and self.alarm_ignition_enabled
        elif _alert_type == 9:               # Drop Alert
            return self.has_alarm_drop and self.alarm_drop_enabled
        elif _alert_type == 13:              # Voltage Alert
            return self.has_alarm_voltage and self.alarm_voltage_enabled
        else:
            _LOGGER.error("Unknown alert type: %s", _alert_type)
            return False


class PajGPSAlert:
    """Representation of single Paj GPS notification/alert."""

    device_id: int
    alert_type: int

    def __init__(self, device_id: int, alert_type: int) -> None:
        """Initialize the PajGPSAlert class."""
        self.device_id = device_id
        self.alert_type = alert_type


class PajGPSPositionData:
    """Representation of single Paj GPS device tracking data."""

    device_id: int
    lat: float
    lng: float
    elevation: float | None = None
    direction: int
    speed: int
    battery: int
    last_elevation_update: float = 0.0

    def __init__(self, device_id: int, lat: float, lng: float, direction: int, speed: int, battery: int) -> None:
        """Initialize the PajGPSPositionData class."""
        self.device_id = device_id
        self.lat = lat
        self.lng = lng
        self.direction = direction
        self.speed = speed
        self.battery = battery


class PajGPSSensorData:
    """Representation of single Paj GPS device sensor data."""

    device_id: int
    voltage: float = 0.0
    total_update_time_ms: float = 0.0   # Total time for full PajGPS data update in milliseconds

