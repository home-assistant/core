"""Test sensor of NextDNS integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from nextdns import ApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Test states of sensors."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_nextdns_client: AsyncMock,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service causes an error."""
    with patch("homeassistant.components.nextdns.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    entity_ids = (entry.entity_id for entry in entity_entries)

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=10))
    mock_nextdns_client.get_analytics_status.side_effect = ApiError("API Error")
    mock_nextdns_client.get_analytics_dnssec.side_effect = ApiError("API Error")
    mock_nextdns_client.get_analytics_encryption.side_effect = ApiError("API Error")
    mock_nextdns_client.get_analytics_ip_versions.side_effect = ApiError("API Error")
    mock_nextdns_client.get_analytics_protocols.side_effect = ApiError("API Error")

    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    freezer.tick(timedelta(minutes=10))
    mock_nextdns_client.get_analytics_status.side_effect = None
    mock_nextdns_client.get_analytics_dnssec.side_effect = None
    mock_nextdns_client.get_analytics_encryption.side_effect = None
    mock_nextdns_client.get_analytics_ip_versions.side_effect = None
    mock_nextdns_client.get_analytics_protocols.side_effect = None

    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
