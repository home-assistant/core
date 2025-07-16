"""Test Tuya climate platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import ManagerCompat
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.CLIMATE in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.CLIMATE not in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE])
async def test_platform_setup_no_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test platform setup without discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_serenelife_slpac905wuk_air_conditioner"],
)
async def test_fan_mode_windspeed(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test fan mode with windspeed."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("climate.air_conditioner")
    assert state is not None, "climate.air_conditioner does not exist"
    assert state.attributes["fan_mode"] == 1
    await hass.services.async_call(
        Platform.CLIMATE,
        "set_fan_mode",
        {
            "entity_id": "climate.air_conditioner",
            "fan_mode": 2,
        },
    )
    await hass.async_block_till_done()

    # Simulate the device reporting the new windspeed
    mock_device.status["windspeed"] = 2
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "climate.air_conditioner"},
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.air_conditioner")
    assert state is not None, (
        "climate.air_conditioner does not exist after service call"
    )
    assert state.attributes["fan_mode"] == 2


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_serenelife_slpac905wuk_air_conditioner"],
)
async def test_fan_mode_no_valid_code(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test fan mode with no valid code."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("climate.air_conditioner")
    assert state is not None, "climate.air_conditioner does not exist"
    assert state.attributes["fan_mode"] == 1
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.CLIMATE,
            "set_fan_mode",
            {
                "entity_id": "climate.air_conditioner",
                "fan_mode": 2,
            },
        )
