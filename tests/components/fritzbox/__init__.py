"""Tests for the AVM Fritz!Box integration."""
from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from homeassistant.components.climate import PRESET_COMFORT, PRESET_ECO
from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import (
    CONF_FAKE_AIN,
    CONF_FAKE_MANUFACTURER,
    CONF_FAKE_NAME,
    CONF_FAKE_PRODUCTNAME,
)

from tests.common import MockConfigEntry


async def setup_config_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    unique_id: str = "any",
    device: Mock = None,
    fritz: Mock = None,
    template: Mock = None,
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

    if template is not None and fritz is not None:
        fritz().get_templates.return_value = [template]

    result = await hass.config_entries.async_setup(entry.entry_id)
    if device is not None:
        await hass.async_block_till_done()
    return result


def set_devices(
    fritz: Mock, devices: list[Mock] | None = None, templates: list[Mock] | None = None
) -> None:
    """Set list of devices or templates."""
    if devices is not None:
        fritz().get_devices.return_value = devices

    if templates is not None:
        fritz().get_templates.return_value = templates


class FritzEntityBaseMock(Mock):
    """base mock of a AVM Fritz!Box binary sensor device."""

    ain = CONF_FAKE_AIN
    manufacturer = CONF_FAKE_MANUFACTURER
    name = CONF_FAKE_NAME
    productname = CONF_FAKE_PRODUCTNAME
    rel_humidity = None
    battery_level = None


class FritzDeviceBinarySensorMock(FritzEntityBaseMock):
    """Mock of a AVM Fritz!Box binary sensor device."""

    alert_state = "fake_state"
    battery_level = 23
    fw_version = "1.2.3"
    has_alarm = True
    has_powermeter = False
    has_switch = False
    has_lightbulb = False
    has_temperature_sensor = False
    has_thermostat = False
    has_blind = False
    present = True


class FritzDeviceClimateMock(FritzEntityBaseMock):
    """Mock of a AVM Fritz!Box climate device."""

    actual_temperature = 18.0
    temperature = 18.0
    alert_state = "fake_state"
    battery_level = 23
    battery_low = True
    comfort_temperature = 22.0
    device_lock = "fake_locked_device"
    eco_temperature = 16.0
    fw_version = "1.2.3"
    has_alarm = False
    has_powermeter = False
    has_lightbulb = False
    has_switch = False
    has_temperature_sensor = True
    has_thermostat = True
    has_blind = False
    holiday_active = "fake_holiday"
    lock = "fake_locked"
    present = True
    summer_active = "fake_summer"
    target_temperature = 19.5
    window_open = "fake_window"
    nextchange_temperature = 22.0
    nextchange_endperiod = 0
    nextchange_preset = PRESET_COMFORT
    scheduled_preset = PRESET_ECO


class FritzDeviceSensorMock(FritzEntityBaseMock):
    """Mock of a AVM Fritz!Box sensor device."""

    battery_level = 23
    device_lock = "fake_locked_device"
    fw_version = "1.2.3"
    has_alarm = False
    has_powermeter = False
    has_lightbulb = False
    has_switch = False
    has_temperature_sensor = True
    has_thermostat = False
    has_blind = False
    lock = "fake_locked"
    present = True
    temperature = 1.23
    rel_humidity = 42


class FritzDeviceSwitchMock(FritzEntityBaseMock):
    """Mock of a AVM Fritz!Box switch device."""

    battery_level = None
    device_lock = "fake_locked_device"
    energy = 1234
    voltage = 230000
    current = 25
    fw_version = "1.2.3"
    has_alarm = False
    has_powermeter = True
    has_lightbulb = False
    has_switch = True
    has_temperature_sensor = True
    has_thermostat = False
    has_blind = False
    switch_state = "fake_state"
    lock = "fake_locked"
    power = 5678
    present = True
    temperature = 1.23


class FritzDeviceLightMock(FritzEntityBaseMock):
    """Mock of a AVM Fritz!Box light device."""

    fw_version = "1.2.3"
    has_alarm = False
    has_powermeter = False
    has_lightbulb = True
    has_color = True
    has_level = True
    has_switch = False
    has_temperature_sensor = False
    has_thermostat = False
    has_blind = False
    level = 100
    present = True
    state = True


class FritzDeviceCoverMock(FritzEntityBaseMock):
    """Mock of a AVM Fritz!Box cover device."""

    fw_version = "1.2.3"
    has_alarm = False
    has_powermeter = False
    has_lightbulb = False
    has_switch = False
    has_temperature_sensor = False
    has_thermostat = False
    has_blind = True
    levelpercentage = 0
