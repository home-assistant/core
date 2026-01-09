"""Tests for the HDFury switch platform."""

from unittest.mock import AsyncMock

from hdfury import HDFuryError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switch_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test HDFury switch entities."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method", "service"),
    [
        (
            "switch.hdfury_vrroom_02_auto_switch_inputs",
            "set_auto_switch_inputs",
            "turn_on",
        ),
        (
            "switch.hdfury_vrroom_02_auto_switch_inputs",
            "set_auto_switch_inputs",
            "turn_off",
        ),
        ("switch.hdfury_vrroom_02_oled_display", "set_oled", "turn_on"),
        ("switch.hdfury_vrroom_02_oled_display", "set_oled", "turn_off"),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    service: str,
) -> None:
    """Test turning device switches on and off."""

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    await hass.services.async_call(
        "switch",
        service,
        {"entity_id": entity_id},
        blocking=True,
    )

    getattr(mock_hdfury_client, method).assert_awaited_once()


@pytest.mark.parametrize(
    ("service", "method"),
    [
        ("turn_on", "set_auto_switch_inputs"),
        ("turn_off", "set_auto_switch_inputs"),
    ],
)
async def test_switch_turn_error(
    hass: HomeAssistant,
    mock_hdfury_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test switch turn on/off raises HomeAssistantError on API failure."""

    getattr(mock_hdfury_client, method).side_effect = HDFuryError()

    await setup_integration(hass, mock_config_entry, [Platform.SWITCH])

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            service,
            {"entity_id": "switch.hdfury_vrroom_02_auto_switch_inputs"},
            blocking=True,
        )
