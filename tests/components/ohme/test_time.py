"""Tests for time."""

from unittest.mock import MagicMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the Ohme sensors."""
    with patch("homeassistant.components.ohme.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test the time set."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={
            ATTR_TIME: "00:00:00",
        },
        target={
            ATTR_ENTITY_ID: "time.ohme_home_pro_target_time",
        },
        blocking=True,
    )

    assert len(mock_client.async_set_target.mock_calls) == 1
