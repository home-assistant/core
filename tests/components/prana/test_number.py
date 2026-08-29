"""Integration-style tests for Prana numbers."""

from unittest.mock import MagicMock, patch

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

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_numbers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_prana_api: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Prana numbers snapshot."""
    with patch("homeassistant.components.prana.PLATFORMS", [Platform.NUMBER]):
        await async_init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("input_value", "expected_api_value"),
    [
        (0.0, 0),  # 0 -> 0
        (1.0, 1),  # 2^(1-1) -> 1
        (2.0, 2),  # 2^(2-1) -> 2
        (3.0, 4),  # 2^(3-1) -> 4
        (4.0, 8),  # 2^(4-1) -> 8
        (5.0, 16),  # 2^(5-1) -> 16
        (6.0, 32),  # 2^(6-1) -> 32
    ],
)
async def test_number_actions(
    hass: HomeAssistant,
    mock_prana_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    input_value: float,
    expected_api_value: int,
) -> None:
    """Test setting number values calls the API with correct math conversion."""
    await async_init_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entries

    target = "number.prana_recuperator_display_brightness"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: target,
            ATTR_VALUE: input_value,
        },
        blocking=True,
    )

    mock_prana_api.set_brightness.assert_called_with(expected_api_value)
