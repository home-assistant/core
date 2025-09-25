"""Test Tuya climate platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "extra_kwargs", "commands"),
    [
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            {ATTR_TEMPERATURE: 22.7},
            [{"code": "temp_set", "value": 22}],
        ),
        (
            "wk_ccpwojhalfxryigz",
            "climate.boiler_temperature_controller",
            {ATTR_TARGET_TEMP_HIGH: 22.7, ATTR_TARGET_TEMP_LOW: 20.2},
            [
                # On this device, the values are inverted
                {"code": "upper_temp", "value": 202},
                {"code": "lower_temp", "value": 227},
            ],
        ),
        (
            "wk_gogb05wrtredz3bs",
            "climate.smart_thermostats",
            {ATTR_TEMPERATURE: 22.7},
            [{"code": "temp_set", "value": 22}],
        ),
        (
            "wk_gogb05wrtredz3bs",
            "climate.smart_thermostats",
            {ATTR_TARGET_TEMP_HIGH: 22.7, ATTR_TARGET_TEMP_LOW: 20.2},
            [
                {"code": "lower_temp", "value": 20},
                {"code": "upper_temp", "value": 22},
            ],
        ),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    extra_kwargs: dict[str, Any],
    commands: list[dict[str, Any]],
) -> None:
    """Test set temperature service."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, **extra_kwargs},
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(mock_device.id, commands)


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_5wnlzekkstwcdsvm"],
)
async def test_fan_mode_windspeed(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test fan mode with windspeed."""
    entity_id = "climate.air_conditioner"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.attributes[ATTR_FAN_MODE] == 1
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_FAN_MODE: 2,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "windspeed", "value": "2"}]
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_5wnlzekkstwcdsvm"],
)
async def test_fan_mode_no_valid_code(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test fan mode with no valid code."""
    # Remove windspeed DPCode to simulate a device with no valid fan mode
    mock_device.function.pop("windspeed", None)
    mock_device.status_range.pop("windspeed", None)
    mock_device.status.pop("windspeed", None)

    entity_id = "climate.air_conditioner"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.attributes.get(ATTR_FAN_MODE) is None
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_FAN_MODE: 2,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_5wnlzekkstwcdsvm"],
)
async def test_set_humidity_not_supported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set humidity service (not available on this device)."""
    entity_id = "climate.air_conditioner"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_HUMIDITY: 50,
            },
            blocking=True,
        )
