"""Test IntelliClima Select."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from pyintelliclima.const import FanMode, FanSpeed
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

SELECT_ENTITY_ID = "select.test_vmc_fan_direction_mode"


@pytest.fixture(autouse=True)
async def setup_intelliclima_select_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the select platform."""
    with (
        patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.SELECT]),
    ):
        await setup_integration(hass, mock_config_entry)
        # Let tests run against this initialized state
        yield


async def test_all_select_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # There should be exactly one select entity
    select_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == SELECT_DOMAIN
    ]
    assert len(select_entries) == 1

    entity_entry = select_entries[0]
    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("option", "expected_mode"),
    [
        ("forward", FanMode.inward),
        ("reverse", FanMode.outward),
        ("alternate", FanMode.alternate),
        ("sensor", FanMode.sensor),
    ],
)
async def test_select_option_keeps_current_speed(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    option: str,
    expected_mode: FanMode,
) -> None:
    """Selecting any valid option retains the current speed and calls set_mode_speed."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )
    # Device starts with speed_set=FanSpeed.medium (from single_eco_device in conftest),
    # mode is not off and not auto, so current speed is preserved.
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", expected_mode, FanSpeed.medium
    )


async def test_select_option_when_off_defaults_speed_to_sleep(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    single_eco_device,
) -> None:
    """When the device is off, selecting an option defaults the speed to FanSpeed.sleep."""
    # Mutate the shared fixture object – coordinator.data points to the same reference.
    eco = list(single_eco_device.ecocomfort2_devices.values())[0]
    eco.mode_set = FanMode.off

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "forward"},
        blocking=True,
    )
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", FanMode.inward, FanSpeed.sleep
    )


async def test_select_option_in_auto_mode_defaults_speed_to_sleep(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    single_eco_device,
) -> None:
    """When speed_set is FanSpeed.auto_get (auto preset), selecting an option defaults to sleep speed."""
    eco = list(single_eco_device.ecocomfort2_devices.values())[0]
    eco.speed_set = FanSpeed.auto_get
    eco.mode_set = FanMode.sensor

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "reverse"},
        blocking=True,
    )
    mock_cloud_interface.ecocomfort.set_mode_speed.assert_awaited_once_with(
        "11223344", FanMode.outward, FanSpeed.sleep
    )


@pytest.mark.parametrize("option", ["forward", "reverse", "alternate", "sensor"])
async def test_select_option_does_not_call_turn_off(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    option: str,
) -> None:
    """Selecting an option should never call turn_off."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )
    mock_cloud_interface.ecocomfort.turn_off.assert_not_awaited()


async def test_select_option_triggers_coordinator_refresh(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Selecting an option should trigger a coordinator refresh after the API call."""
    initial_call_count = mock_cloud_interface.get_all_device_status.call_count

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "sensor"},
        blocking=True,
    )
    # A refresh must have been requested, so the status fetch count increases.
    assert mock_cloud_interface.get_all_device_status.call_count > initial_call_count
