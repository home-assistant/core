"""Tests for numbers."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from ohme import ApiException
from syrupy import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
    ATTR_VALUE,
)

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Ohme sensors."""
    with patch("homeassistant.components.ohme.PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the number set."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={
            ATTR_VALUE: 100,
        },
        target={
            ATTR_ENTITY_ID: "number.ohme_home_pro_target_percentage",
        },
        blocking=True,
    )

    assert len(mock_client.async_set_target.mock_calls) == 1
