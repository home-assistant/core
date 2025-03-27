"""Tests for the Overseerr sensor platform."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.overseerr import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import call_webhook, setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform
from tests.typing import ClientSessionGenerator


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.overseerr.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_webhook_trigger_update(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.overseerr_available_requests").state == "8"

    mock_overseerr_client.get_request_count.return_value.available = 7
    client = await hass_client_no_auth()

    await call_webhook(
        hass,
        load_json_object_fixture("webhook_request_automatically_approved.json", DOMAIN),
        client,
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.overseerr_available_requests").state == "7"
