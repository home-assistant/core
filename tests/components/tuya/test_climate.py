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
    "mock_device_code",
    ["kt_5wnlzekkstwcdsvm"],
)
@pytest.mark.parametrize(
    ("service", "service_data", "expected_command"),
    [
        (
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 22.7},
            {"code": "temp_set", "value": 23},
        ),
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: 2},
            {"code": "windspeed", "value": "2"},
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
    expected_command: dict[str, Any],
) -> None:
    """Test service action."""
    entity_id = "climate.air_conditioner"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
            **service_data,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [expected_command]
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_5wnlzekkstwcdsvm"],
)
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: 2},
        ),
        (
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: 50},
        ),
    ],
)
async def test_action_not_supported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service action not supported."""
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
            service,
            {
                ATTR_ENTITY_ID: entity_id,
                **service_data,
            },
            blocking=True,
        )
