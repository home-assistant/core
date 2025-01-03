"""Tests for the Overseerr services."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.overseerr.const import ATTR_CONFIG_ENTRY_ID, DOMAIN
from homeassistant.components.overseerr.services import SERVICE_GET_REQUESTS
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_service_get_requests(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the get_requests service."""

    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_REQUESTS,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
