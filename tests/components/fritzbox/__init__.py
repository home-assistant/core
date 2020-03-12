"""Tests for the FritzBox! integration."""
from unittest.mock import Mock


class FritzDeviceBinarySensorMock(Mock):
    """Mock of a AVM Fritz!Box binary sensor device."""

    ain = "fake_ain"
    alert_state = "fake_state"
    fw_version = "1.2.3"
    has_alarm = True
    has_switch = False
    has_temperature_sensor = False
    has_thermostat = False
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    present = True
    productname = "fake_productname"


class FritzDeviceSensorMock(Mock):
    """Mock of a AVM Fritz!Box sensor device."""

    ain = "fake_ain"
    device_lock = "fake_locked_device"
    fw_version = "1.2.3"
    has_alarm = False
    has_switch = False
    has_temperature_sensor = True
    has_thermostat = False
    lock = "fake_locked"
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    present = True
    productname = "fake_productname"
    temperature = 1.23


class FritzDeviceSwitchMock(Mock):
    """Mock of a AVM Fritz!Box switch device."""

    ain = "fake_ain"
    device_lock = "fake_locked_device"
    energy = 1234
    fw_version = "1.2.3"
    has_alarm = False
    has_switch = True
    has_temperature_sensor = True
    has_thermostat = False
    switch_state = "fake_state"
    lock = "fake_locked"
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    power = 5678
    present = True
    productname = "fake_productname"
    temperature = 135
