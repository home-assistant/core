"""Tests for the FritzBox! integration."""
from unittest.mock import Mock


class FritzDeviceSwitchMock(Mock):
    """Mock of a AVM Fritz!Box switch device."""

    ain = "fake_ain"
    device_lock = True
    energy = 1234
    has_alarm = False
    has_switch = True
    has_temperature_sensor = True
    has_thermostat = False
    is_on = True
    lock = True
    name = "fake_name"
    power = 5678
    present = True
    temperature = 135
