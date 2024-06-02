"""Test entity availability."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pydrawise.schema import Controller
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hydrawise.const import SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    ("platform"),
    [
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.SENSOR,
    ],
)
async def test_controller_offline(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    controller: Controller,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Test availability for sensors when controller is offline."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [platform],
    ):
        config_entry = await mock_add_config_entry()
        controller.online = False
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("platform"),
    [
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.SENSOR,
    ],
)
async def test_api_offline(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
    entity_registry: er.EntityRegistry,
    mock_pydrawise: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    platform: Platform,
) -> None:
    """Test availability of sensors when API call fails."""
    with patch(
        "homeassistant.components.hydrawise.PLATFORMS",
        [platform],
    ):
        config_entry = await mock_add_config_entry()
        mock_pydrawise.get_user.reset_mock(return_value=True)
        mock_pydrawise.get_user.side_effect = ClientError
        freezer.tick(SCAN_INTERVAL + timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
