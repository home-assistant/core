"""Test IntelliClima Fans."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FAN_ENTITY_ID = "fan.test_vmc"


@pytest.fixture(autouse=True)
async def setup_intelliclima_fan_only(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the fan platform."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)
        # Let tests run against this initialized state
        yield


async def test_all_fan_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_current: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_current.entry_id
    )

    # There should be exactly one fan entity
    fan_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == "fan"
    ]
    assert len(fan_entries) == 1
    entity_entry = fan_entries[0]

    # Device should exist and match snapshot
    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


async def test_fan_initial_state(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Verify initial fan state, percentage and preset."""
    state = hass.states.get(FAN_ENTITY_ID)
    assert state is not None

    # Name and basic state come from IntelliClimaVMCFan and single_eco_device.
    assert state.name == "Test VMC"
    assert state.state == "on"
    # single_eco_device has speed_set="3" (medium) and mode_set="1" (in / forward).
    assert state.attributes["percentage"] == 75
    assert state.attributes["preset_mode"] == "forward"


async def test_fan_turn_off_service_calls_api(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.turn_off should call ecocomfort.turn_off and refresh."""
    await hass.services.async_call(
        "fan",
        "turn_off",
        {"entity_id": FAN_ENTITY_ID},
        blocking=True,
    )

    # Device serial from single_eco_device.crono_sn
    mock_cloud_interface.ecocomfort.turn_off.assert_awaited_once_with("11223344")
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_not_awaited()


async def test_fan_turn_on_service_calls_api(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.turn_on should call ecocomfort.turn_on and refresh."""
    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": FAN_ENTITY_ID, "percentage": 30, "preset_mode": "alternate"},
        blocking=True,
    )

    # Device serial from single_eco_device.crono_sn
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", "3", "2"
    )


async def test_fan_set_percentage_maps_to_speed(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.set_percentage maps to closest IntelliClima speed via set_mode_speed."""
    # 15% is closest to 25% (sleep).
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": FAN_ENTITY_ID, "percentage": 15},
        blocking=True,
    )
    # Initial mode_set="1" (forward) from single_eco_device.
    # Sleep speed is "1" (25%).
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", "1", "1"
    )


async def test_fan_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Setting percentage to 0 should call turn_off, not set_mode_speed."""
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": FAN_ENTITY_ID, "percentage": 0},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort.turn_off.assert_awaited_once_with("11223344")
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_not_awaited()


@pytest.mark.parametrize(
    ("percentage", "preset_mode", "expected_mode", "expected_speed"),
    [
        # percentage=None, preset_mode=None -> defaults to previous speed > 75% (sleep),
        # previous mode > "alternate"
        (None, None, "1", "3"),
        # percentage=0, preset_mode=None -> also default 25% (sleep), alternate mode
        (0, None, "1", "1"),
    ],
)
async def test_fan_turn_on_defaulting_behavior(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    percentage: int | None,
    preset_mode: str | None,
    expected_mode: str,
    expected_speed: str,
) -> None:
    """turn_on defaults percentage/preset as expected."""
    data: dict = {"entity_id": FAN_ENTITY_ID}
    if percentage is not None:
        data["percentage"] = percentage
    if preset_mode is not None:
        data["preset_mode"] = preset_mode

    await hass.services.async_call(
        "fan",
        "turn_on",
        data,
        blocking=True,
    )

    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", expected_mode, expected_speed
    )
    mock_cloud_interface.ecocomfort.turn_off.assert_not_awaited()
