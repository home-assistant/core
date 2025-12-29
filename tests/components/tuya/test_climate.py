"""Test Tuya climate platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_STEP,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

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


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE])
async def test_us_customary_system(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    for entity in entity_registry.entities.values():
        state = hass.states.get(entity.entity_id)
        assert state.attributes == snapshot(
            name=entity.entity_id,
            include=props(
                ATTR_CURRENT_TEMPERATURE,
                ATTR_MAX_TEMP,
                ATTR_MIN_TEMP,
                ATTR_TARGET_TEMP_STEP,
                ATTR_TEMPERATURE,
            ),
        )


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "service", "service_data", "expected_commands"),
    [
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 22.7},
            [{"code": "temp_set", "value": 23}],
        ),
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: 2},
            [{"code": "windspeed", "value": "2"}],
        ),
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_TURN_ON,
            {},
            [{"code": "switch", "value": True}],
        ),
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_TURN_OFF,
            {},
            [{"code": "switch", "value": False}],
        ),
        (
            "kt_ibmmirhhq62mmf1g",
            "climate.master_bedroom_ac",
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [{"code": "switch", "value": True}, {"code": "mode", "value": "cold"}],
        ),
        (
            "wk_gc1bxoq2hafxpa35",
            "climate.polotentsosushitel",
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "holiday"},
            [{"code": "mode", "value": "holiday"}],
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    service: str,
    service_data: dict[str, Any],
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test climate action."""
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
        mock_device.id, expected_commands
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
