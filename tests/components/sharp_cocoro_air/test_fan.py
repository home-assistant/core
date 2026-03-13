"""Test the Sharp COCORO Air fan platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DEVICE_1

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def fan_only() -> Generator[None]:
    """Enable only the fan platform."""
    with patch(
        "homeassistant.components.sharp_cocoro_air.PLATFORMS",
        [Platform.FAN],
    ):
        yield


@pytest.mark.usefixtures("mock_sharp_api")
async def test_fan_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test all fan entity states."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fan_turn_on(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the fan."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.living_room_purifier"},
        blocking=True,
    )

    mock_sharp_api.power_on.assert_awaited_once_with(DEVICE_1)

    state = hass.states.get("fan.living_room_purifier")
    assert state is not None
    assert state.state == "on"


async def test_fan_turn_off(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off the fan."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.living_room_purifier"},
        blocking=True,
    )

    mock_sharp_api.power_off.assert_awaited_once_with(DEVICE_1)

    state = hass.states.get("fan.living_room_purifier")
    assert state is not None
    assert state.state == "off"


async def test_fan_set_preset_mode(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a preset mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "fan.living_room_purifier",
            ATTR_PRESET_MODE: "night",
        },
        blocking=True,
    )

    mock_sharp_api.set_mode.assert_awaited_once_with(DEVICE_1, "night")


async def test_fan_turn_on_with_preset(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with a preset mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "fan.living_room_purifier",
            ATTR_PRESET_MODE: "pollen",
        },
        blocking=True,
    )

    mock_sharp_api.power_on.assert_awaited_once_with(DEVICE_1)
    mock_sharp_api.set_mode.assert_awaited_once_with(DEVICE_1, "pollen")


async def test_fan_properties_when_off(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fan entity when device is powered off."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("fan.bedroom_purifier")
    assert state is not None
    assert state.state == "off"
