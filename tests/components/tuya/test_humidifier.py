"""Test Tuya humidifier platform."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.humidifier import (
    DOMAIN as HUMIDIFIER_DOMAIN,
    HumidifierService,
    HumidifierServiceArgument,
)
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.HUMIDIFIER]):
        yield


@pytest.mark.usefixtures("no_quirk")
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
    ["cs_zibqa9dutqyaxym2"],
)
@pytest.mark.parametrize(
    ("service", "service_data", "expected_command"),
    [
        (HumidifierService.TURN_ON, {}, {"code": "switch", "value": True}),
        (HumidifierService.TURN_OFF, {}, {"code": "switch", "value": False}),
        (
            HumidifierService.SET_HUMIDITY,
            {HumidifierServiceArgument.HUMIDITY: 50},
            {"code": "dehumidify_set_value", "value": 50},
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
    """Test humidifier action."""
    entity_id = "humidifier.dehumidifier"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        service,
        {
            TargetKey.ENTITY_ID: entity_id,
            **service_data,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [expected_command]
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["cs_zibqa9dutqyaxym2"],
)
@pytest.mark.parametrize(
    ("service", "service_data", "translation_placeholders"),
    [
        (
            HumidifierService.TURN_ON,
            {},
            {
                "expected": "['switch', 'switch_spray']",
                "available": ("['child_lock', 'countdown_set']"),
            },
        ),
        (
            HumidifierService.TURN_OFF,
            {},
            {
                "expected": "['switch', 'switch_spray']",
                "available": ("['child_lock', 'countdown_set']"),
            },
        ),
        (
            HumidifierService.SET_HUMIDITY,
            {HumidifierServiceArgument.HUMIDITY: 50},
            {
                "expected": "['dehumidify_set_value']",
                "available": ("['child_lock', 'countdown_set']"),
            },
        ),
    ],
)
async def test_action_unsupported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
    translation_placeholders: dict[str, Any],
) -> None:
    """Test service actions when not supported by the device."""
    # Remove switch control and dehumidify_set_value - but keep other functionality
    mock_device.status.pop("switch")
    mock_device.function.pop("switch")
    mock_device.status_range.pop("switch")
    mock_device.status.pop("dehumidify_set_value")
    mock_device.function.pop("dehumidify_set_value")
    mock_device.status_range.pop("dehumidify_set_value")

    entity_id = "humidifier.dehumidifier"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            service,
            {
                TargetKey.ENTITY_ID: entity_id,
                **service_data,
            },
            blocking=True,
        )
    assert err.value.translation_key == "action_dpcode_not_found"
    assert err.value.translation_placeholders == translation_placeholders
