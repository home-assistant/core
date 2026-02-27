"""Test the Sharp COCORO Air switch platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
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
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.sharp_cocoro_air.PLATFORMS",
        [Platform.SWITCH],
    ):
        yield


@pytest.mark.usefixtures("mock_sharp_api")
async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test all switch entity states."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_turn_on(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the humidification switch."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.living_room_purifier_humidification"},
        blocking=True,
    )

    mock_sharp_api.set_humidify.assert_awaited_once_with(DEVICE_1, True)

    state = hass.states.get("switch.living_room_purifier_humidification")
    assert state is not None
    assert state.state == "on"


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_sharp_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off the humidification switch."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.living_room_purifier_humidification"},
        blocking=True,
    )

    mock_sharp_api.set_humidify.assert_awaited_once_with(DEVICE_1, False)

    state = hass.states.get("switch.living_room_purifier_humidification")
    assert state is not None
    assert state.state == "off"
