"""Tests for the AVM Fritz!Box integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    DOMAIN: {
        CONF_DEVICES: [
            {
                CONF_HOST: "fake_host",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
            }
        ]
    }
}


async def setup_config_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    unique_id: str = "any",
    device: Mock = None,
    fritz: Mock = None,
) -> bool:
    """Do setup of a MockConfigEntry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)
    if device is not None and fritz is not None:
        fritz().get_devices.return_value = [device]
    result = await hass.config_entries.async_setup(entry.entry_id)
    if device is not None:
        await hass.async_block_till_done()
    return result


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


class FritzDeviceClimateMock(Mock):
    """Mock of a AVM Fritz!Box climate device."""

    actual_temperature = 18.0
    ain = "fake_ain"
    alert_state = "fake_state"
    battery_level = 23
    battery_low = True
    comfort_temperature = 22.0
    device_lock = "fake_locked_device"
    eco_temperature = 16.0
    fw_version = "1.2.3"
    has_alarm = False
    has_switch = False
    has_temperature_sensor = False
    has_thermostat = True
    holiday_active = "fake_holiday"
    lock = "fake_locked"
    manufacturer = "fake_manufacturer"
    name = "fake_name"
    present = True
    productname = "fake_productname"
    summer_active = "fake_summer"
    target_temperature = 19.5
    window_open = "fake_window"


class FritzDeviceSensorMock(Mock):
    """Mock of a AVM Fritz!Box sensor device."""

    ain = "fake_ain"
    battery_level = 23
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
