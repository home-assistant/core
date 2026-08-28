"""Tests for the Fumis switch entities."""

from unittest.mock import MagicMock

from fumis import FumisConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fumis.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import UNIQUE_ID

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.parametrize(
    "init_integration", [Platform.SWITCH], indirect=True
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fumis switch entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_eco_mode_turn_on(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test turning on eco mode."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.clou_duo_eco_mode"},
        blocking=True,
    )

    mock_fumis.set_eco_mode.assert_called_once_with(enabled=True)


@pytest.mark.usefixtures("init_integration")
async def test_eco_mode_turn_off(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test turning off eco mode."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.clou_duo_eco_mode"},
        blocking=True,
    )

    mock_fumis.set_eco_mode.assert_called_once_with(enabled=False)


@pytest.mark.usefixtures("init_integration")
async def test_timer_turn_on(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test turning on the timer."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.clou_duo_timer"},
        blocking=True,
    )

    mock_fumis.set_timer.assert_called_once_with(enabled=True)


@pytest.mark.usefixtures("init_integration")
async def test_timer_turn_off(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test turning off the timer."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.clou_duo_timer"},
        blocking=True,
    )

    mock_fumis.set_timer.assert_called_once_with(enabled=False)


@pytest.mark.usefixtures("init_integration")
async def test_switch_error_handling(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test error handling for switch actions."""
    mock_fumis.set_eco_mode.side_effect = FumisConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.clou_duo_eco_mode"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"


@pytest.mark.parametrize("device_fixture", ["info_minimal"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_switches_conditional_creation(
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test eco_mode switch is not created when data is missing."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    unique_ids = {entry.unique_id for entry in entity_entries}

    # Eco mode should NOT exist with the minimal fixture
    assert f"{UNIQUE_ID}_eco_mode" not in unique_ids

    # Timer should still exist
    assert f"{UNIQUE_ID}_timer" in unique_ids
