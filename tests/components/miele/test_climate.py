"""Tests for miele climate module."""

from unittest.mock import MagicMock

from aiohttp import ClientError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TEST_PLATFORM = Platform.CLIMATE
pytestmark = [
    pytest.mark.parametrize("platforms", [(TEST_PLATFORM,)]),
    pytest.mark.parametrize(
        "load_action_file",
        ["action_freezer.json"],
        ids=[
            "freezer",
        ],
    ),
]

ENTITY_ID = "climate.freezer_freezer"


async def test_climate_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test climate entity state."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_target(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test the climate can be turned on/off."""

    await hass.services.async_call(
        TEST_PLATFORM,
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, "temperature": -17},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_miele_client.set_target_temperature.assert_called_once()


async def test_api_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test handling of exception from API."""
    mock_miele_client.set_target_temperature.side_effect = ClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TEST_PLATFORM,
            "set_temperature",
            {ATTR_ENTITY_ID: ENTITY_ID, "temperature": -17},
            blocking=True,
        )
    mock_miele_client.set_target_temperature.assert_called_once()
