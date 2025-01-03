"""Tests for the IronOS select platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from enum import Enum
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pynecil import (
    AnimationSpeed,
    BatteryType,
    CharSetting,
    CommunicationError,
    LockingMode,
    LogoDuration,
    ScreenOrientationMode,
    ScrollSpeed,
    TempUnit,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
async def select_only() -> AsyncGenerator[None]:
    """Enable only the select platform."""
    with patch(
        "homeassistant.components.iron_os.PLATFORMS",
        [Platform.SELECT],
    ):
        yield


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_pynecil", "ble_device"
)
async def test_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the IronOS select platform states."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "option", "call_params"),
    [
        (
            "select.pinecil_power_source",
            "battery_3s",
            (CharSetting.MIN_DC_VOLTAGE_CELLS, BatteryType.BATTERY_3S),
        ),
        (
            "select.pinecil_display_orientation_mode",
            "right_handed",
            (CharSetting.ORIENTATION_MODE, ScreenOrientationMode.RIGHT_HANDED),
        ),
        (
            "select.pinecil_animation_speed",
            "medium",
            (CharSetting.ANIMATION_SPEED, AnimationSpeed.MEDIUM),
        ),
        (
            "select.pinecil_temperature_display_unit",
            "fahrenheit",
            (CharSetting.TEMP_UNIT, TempUnit.FAHRENHEIT),
        ),
        (
            "select.pinecil_scrolling_speed",
            "fast",
            (CharSetting.DESC_SCROLL_SPEED, ScrollSpeed.FAST),
        ),
        (
            "select.pinecil_button_locking_mode",
            "full_locking",
            (CharSetting.LOCKING_MODE, LockingMode.FULL_LOCKING),
        ),
        (
            "select.pinecil_boot_logo_duration",
            "loop",
            (CharSetting.LOGO_DURATION, LogoDuration.LOOP),
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_select_option(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    entity_id: str,
    option: str,
    call_params: tuple[Enum, ...],
) -> None:
    """Test the IronOS select option service."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: option},
        target={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(mock_pynecil.write.mock_calls) == 1
    mock_pynecil.write.assert_called_once_with(*call_params)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_select_option_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
) -> None:
    """Test the IronOS select option service exception."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_pynecil.write.side_effect = CommunicationError

    with pytest.raises(
        ServiceValidationError,
        match="Failed to submit setting to device, try again later",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            service_data={ATTR_OPTION: "battery_3s"},
            target={ATTR_ENTITY_ID: "select.pinecil_power_source"},
            blocking=True,
        )
