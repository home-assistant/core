"""Test the Home Assistant analytics sensor module."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from python_homeassistant_analytics import (
    HomeassistantAnalyticsConnectionError,
    HomeassistantAnalyticsError,
    HomeassistantAnalyticsNotModifiedError,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.analytics_insights.coordinator import RETRY_AFTER
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_analytics_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.analytics_insights.PLATFORMS",
        [Platform.SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(HomeassistantAnalyticsConnectionError(), id="connection"),
        pytest.param(
            HomeassistantAnalyticsError("Unexpected response"), id="bad_response"
        ),
    ],
)
async def test_update_error_recovers(
    hass: HomeAssistant,
    mock_analytics_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: HomeassistantAnalyticsError,
) -> None:
    """Test entities go unavailable on error and recover after the retry delay."""
    await setup_integration(hass, mock_config_entry)

    mock_analytics_client.get_current_analytics.side_effect = exception
    freezer.tick(delta=timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.homeassistant_analytics_spotify").state
        == STATE_UNAVAILABLE
    )

    mock_analytics_client.get_current_analytics.side_effect = None
    freezer.tick(delta=RETRY_AFTER)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.homeassistant_analytics_spotify").state == "24388"


async def test_data_not_modified(
    hass: HomeAssistant,
    mock_analytics_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test not updating data if its not modified."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.homeassistant_analytics_spotify").state == "24388"
    mock_analytics_client.get_current_analytics.side_effect = (
        HomeassistantAnalyticsNotModifiedError
    )
    freezer.tick(delta=timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_analytics_client.get_current_analytics.assert_called()
    assert hass.states.get("sensor.homeassistant_analytics_spotify").state == "24388"


async def test_data_not_modified_uses_other_endpoints(
    hass: HomeAssistant,
    mock_analytics_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a 304 on one endpoint does not discard fresh data from the others."""
    await setup_integration(hass, mock_config_entry)

    current = mock_analytics_client.get_current_analytics.return_value
    mock_analytics_client.get_addons.side_effect = (
        HomeassistantAnalyticsNotModifiedError
    )
    mock_analytics_client.get_current_analytics.return_value = replace(
        current, integrations={**current.integrations, "spotify": 1}
    )
    freezer.tick(delta=timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.homeassistant_analytics_core_samba").state == "76357"
    assert hass.states.get("sensor.homeassistant_analytics_spotify").state == "1"
