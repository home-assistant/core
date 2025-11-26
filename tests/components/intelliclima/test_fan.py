"""Test IntelliClima Fans."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_fan_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_current: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry_current.entry_id
        )


async def test_fan_initial_state(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Verify initial fan state, percentage and preset."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

    states = hass.states.async_all("fan")
    assert len(states) == 1
    state = states[0]

    # Name and basic state come from IntelliClimaVMCFan and single_eco_device.
    assert state.name == "Test VMC Fan"
    assert state.state == "on"
    # single_eco_device has speed_set="3" (medium) and mode_set="1" (in / forward).
    assert state.attributes["percentage"] == 75
    assert state.attributes["preset_mode"] == "forward"


async def test_fan_turn_off_service_calls_api(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.turn_off should call ecocomfort.turn_off and refresh."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

    states = hass.states.async_all("fan")
    assert len(states) == 1
    entity_id = states[0].entity_id

    await hass.services.async_call(
        "fan",
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    # Device serial from single_eco_device.crono_sn
    mock_cloud_interface.ecocomfort.turn_off.assert_awaited_once_with("11223344")
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_not_awaited()
    mock_cloud_interface.ecocomfort.set_mode_speed_auto.assert_not_awaited()


async def test_fan_turn_on_service_calls_api(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.turn_on should call ecocomfort.turn_on and refresh."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

    states = hass.states.async_all("fan")
    assert len(states) == 1
    entity_id = states[0].entity_id

    await hass.services.async_call(
        "fan",
        "turn_on",
        {"entity_id": entity_id, "percentage": 30, "preset_mode": "alternate"},
        blocking=True,
    )

    # Device serial from single_eco_device.crono_sn
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", "3", "2"
    )
    mock_cloud_interface.ecocomfort.set_mode_speed_auto.assert_not_awaited()


async def test_fan_set_percentage_maps_to_speed(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.set_percentage maps to closest IntelliClima speed via set_mode_speed."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

    states = hass.states.async_all("fan")
    assert len(states) == 1
    entity_id = states[0].entity_id

    # 15% is closest to 25% (sleep).
    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": entity_id, "percentage": 15},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once()
    device_sn, mode, speed = mock_cloud_interface.ecocomfort.set_mode_speed.call_args[0]
    assert device_sn == "11223344"
    # Initial mode_set="1" (forward) from single_eco_device.
    assert mode == "1"
    # Sleep speed is "1" (25%).
    assert speed == "1"


async def test_fan_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Setting percentage to 0 should call turn_off, not set_mode_speed."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

    states = hass.states.async_all("fan")
    assert len(states) == 1
    entity_id = states[0].entity_id

    await hass.services.async_call(
        "fan",
        "set_percentage",
        {"entity_id": entity_id, "percentage": 0},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort.turn_off.assert_awaited_once_with("11223344")
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_not_awaited()
    mock_cloud_interface.ecocomfort.set_mode_speed_auto.assert_not_awaited()


async def test_fan_set_preset_mode_auto_uses_auto_api(
    hass: HomeAssistant,
    mock_config_entry_current: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Setting preset_mode 'auto' should call set_mode_speed_auto."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry_current)

    states = hass.states.async_all("fan")
    assert len(states) == 1
    entity_id = states[0].entity_id

    await hass.services.async_call(
        "fan",
        "set_preset_mode",
        {"entity_id": entity_id, "preset_mode": "auto"},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort.set_mode_speed_auto.assert_awaited_once_with(
        "11223344"
    )
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_not_awaited()
    mock_cloud_interface.ecocomfort.turn_off.assert_not_awaited()
