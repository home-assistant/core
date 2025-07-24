"""Tests for the Russound RIO number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import NAME_ZONE_1

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.russound_rio.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_suffix", "value", "expected_method", "expected_arg"),
    [
        ("bass", -5, "set_bass", -5),
        ("balance", 3, "set_balance", 3),
        ("treble", 7, "set_treble", 7),
        ("turn_on_volume", 60, "set_turn_on_volume", 30),
    ],
)
async def test_setting_number_value(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_suffix: str,
    value: int,
    expected_method: str,
    expected_arg: int,
) -> None:
    """Test setting value on Russound number entity."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: f"{NUMBER_DOMAIN}.{NAME_ZONE_1}_{entity_suffix}",
            ATTR_VALUE: value,
        },
        blocking=True,
    )

    zone = mock_russound_client.controllers[1].zones[1]
    getattr(zone, expected_method).assert_called_once_with(expected_arg)
