"""Test Tuya button platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "no_quirk")
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


@pytest.mark.parametrize("mock_device_code", ["msp_mzuro9jgjs7uiryn"])
async def test_litter_box_start_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test starting litter box cleaning."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    entity_id = entity_registry.async_get_entity_id(
        BUTTON_DOMAIN, "tuya", f"tuya.{mock_device.id}start"
    )
    assert entity_id is not None

    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {TargetKey.ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "start", "value": True}]
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["sd_lr33znaodtyarrrz"],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test button action."""
    entity_id = "button.v20_reset_duster_cloth"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        BUTTON_DOMAIN,
        ButtonService.PRESS,
        {
            TargetKey.ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "reset_duster_cloth", "value": True}]
    )
