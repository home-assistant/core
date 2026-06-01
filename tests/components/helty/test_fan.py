"""Test the Helty Flow fan platform."""

from unittest.mock import AsyncMock, patch

from pyhelty import FanMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import make_data

from tests.common import MockConfigEntry, snapshot_platform

FAN_ENTITY = "fan.vmc_soggiorno"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.helty.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fan_preset_state(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fan reports an active preset."""
    mock_helty_client.async_get_data.return_value = make_data(fan_mode=FanMode.NIGHT)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(FAN_ENTITY)
    assert state.attributes[ATTR_PRESET_MODE] == "night"
    assert state.attributes[ATTR_PERCENTAGE] is None


async def test_fan_set_preset(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a preset mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(FanMode.BOOST)


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [(25, FanMode.LOW), (50, FanMode.MEDIUM), (75, FanMode.HIGH), (100, FanMode.MAX)],
)
async def test_fan_set_percentage(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    percentage: int,
    expected: FanMode,
) -> None:
    """Test mapping a percentage to a discrete speed."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(expected)


async def test_fan_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting 0% turns the fan off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY, ATTR_PERCENTAGE: 0},
        blocking=True,
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(FanMode.OFF)


async def test_fan_turn_off_and_on(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the fan off and back on."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: FAN_ENTITY}, blocking=True
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(FanMode.OFF)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FAN_ENTITY}, blocking=True
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(FanMode.LOW)


async def test_fan_turn_on_with_percentage(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with an explicit percentage."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY, ATTR_PERCENTAGE: 100},
        blocking=True,
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(FanMode.MAX)


async def test_fan_turn_on_with_preset(
    hass: HomeAssistant,
    mock_helty_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on with an explicit preset."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY, ATTR_PRESET_MODE: "free_cooling"},
        blocking=True,
    )
    mock_helty_client.async_set_fan_mode.assert_awaited_with(FanMode.FREE_COOLING)
