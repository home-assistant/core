"""Tests for the IronOS switch platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pynecil import CharSetting, CommunicationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
async def switch_only() -> AsyncGenerator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.iron_os.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_pynecil", "ble_device"
)
async def test_switch_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the IronOS switch platform."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "target"),
    [
        ("switch.pinecil_animation_loop", CharSetting.ANIMATION_LOOP),
        ("switch.pinecil_calibrate_cjc", CharSetting.CALIBRATE_CJC),
        ("switch.pinecil_cool_down_screen_flashing", CharSetting.COOLING_TEMP_BLINK),
        ("switch.pinecil_detailed_idle_screen", CharSetting.IDLE_SCREEN_DETAILS),
        ("switch.pinecil_detailed_solder_screen", CharSetting.SOLDER_SCREEN_DETAILS),
        ("switch.pinecil_invert_screen", CharSetting.DISPLAY_INVERT),
        ("switch.pinecil_swap_buttons", CharSetting.INVERT_BUTTONS),
    ],
)
@pytest.mark.parametrize(
    ("service", "value"),
    [
        (SERVICE_TOGGLE, False),
        (SERVICE_TURN_OFF, False),
        (SERVICE_TURN_ON, True),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "ble_device")
async def test_turn_on_off_toggle(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    freezer: FrozenDateTimeFactory,
    service: str,
    value: bool,
    entity_id: str,
    target: CharSetting,
) -> None:
    """Test the IronOS switch turn on/off, toggle services."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(mock_pynecil.write.mock_calls) == 1
    mock_pynecil.write.assert_called_once_with(target, value)


@pytest.mark.parametrize(
    "service",
    [SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON],
)
@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "ble_device", "mock_pynecil"
)
async def test_turn_on_off_toggle_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_pynecil: AsyncMock,
    service: str,
) -> None:
    """Test the IronOS switch turn on/off, toggle service exceptions."""

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
            SWITCH_DOMAIN,
            service,
            service_data={ATTR_ENTITY_ID: "switch.pinecil_animation_loop"},
            blocking=True,
        )
