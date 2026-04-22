"""Test Tuya camera platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_device_handlers import TUYA_QUIRKS_REGISTRY
from tuya_device_handlers.definition.camera import CameraQuirk, get_default_definition
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.camera import (
    DOMAIN as CAMERA_DOMAIN,
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with (
        patch("homeassistant.components.tuya.PLATFORMS", [Platform.CAMERA]),
        # Mock camera access token which normally is randomized.
        patch(
            "homeassistant.components.camera.SystemRandom.getrandbits",
            return_value=1,
        ),
    ):
        yield


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

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


@pytest.mark.parametrize("mock_device_code", ["sp_rudejjigkywujjvs"])
@pytest.mark.parametrize(
    ("get_quirks", "available"),
    [
        (None, True),
        ([], False),
        ([CameraQuirk(key="", definition_fn=get_default_definition)], True),
        ([CameraQuirk(key="", definition_fn=lambda d: None)], False),
    ],
)
async def test_empty_quirk(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    get_quirks: list | None,
    available: bool,
) -> None:
    """Test None quirks use defaults and empty quirk list skips default entities."""
    with patch.object(TUYA_QUIRKS_REGISTRY, "get_quirk_for_device") as mock_get_quirk:
        mock_get_quirk.return_value = Mock()
        mock_get_quirk.return_value.camera_quirks = get_quirks
        await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("camera.burocam")
    assert (state is not None) is available


@pytest.mark.parametrize(
    "mock_device_code",
    ["sp_rudejjigkywujjvs"],
)
@pytest.mark.parametrize(
    ("service", "expected_command"),
    [
        (
            SERVICE_DISABLE_MOTION,
            {"code": "motion_switch", "value": False},
        ),
        (
            SERVICE_ENABLE_MOTION,
            {"code": "motion_switch", "value": True},
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    expected_command: dict[str, Any],
) -> None:
    """Test camera action."""
    entity_id = "camera.burocam"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        CAMERA_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [expected_command]
    )
