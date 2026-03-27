"""Test the Eve Online integration setup."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import aiohttp
from eveonline import EveOnlineError
from eveonline.exceptions import EveOnlineAuthenticationError
from eveonline.models import (
    CharacterLocation,
    CharacterShip,
    IndustryJob,
    MarketOrder,
    UniverseName,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .conftest import mock_server_status

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test successful setup of a config entry."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup failure when the API returns an error."""
    mock_eveonline_client.async_get_server_status.side_effect = EveOnlineError(
        "API unavailable"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup failure when authentication fails."""
    mock_eveonline_client.async_get_server_status.side_effect = (
        EveOnlineAuthenticationError("Token expired")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup failure when a network error occurs."""
    mock_eveonline_client.async_get_server_status.side_effect = aiohttp.ClientError(
        "Connection reset"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test successful unloading of a config entry."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_coordinator_optional_endpoint_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that errors on optional endpoints don't fail the coordinator.

    When an optional endpoint raises EveOnlineError, the coordinator
    should still load successfully with None/empty values for that data.
    """
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = EveOnlineError(
        "Endpoint down"
    )
    mock_eveonline_client.async_get_character_online.side_effect = EveOnlineError(
        "Endpoint down"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Optional endpoints should return None, sensor should be unavailable
    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_optional_endpoint_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that aiohttp.ClientError on optional endpoints degrades gracefully."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = aiohttp.ClientError(
        "Connection lost"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_auth_error_on_optional_endpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that auth errors on optional endpoints are not silently swallowed.

    Unlike generic EveOnlineError, EveOnlineAuthenticationError is re-raised
    from _fetch_optional so it propagates upward instead of returning None.
    During first refresh this causes the entry to fail setup (SETUP_RETRY).
    """
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = (
        EveOnlineAuthenticationError("Token revoked")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Auth errors propagate — entry should not be loaded
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_list_endpoint_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that errors on list endpoints return empty lists gracefully."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_skill_queue.side_effect = EveOnlineError(
        "Service unavailable"
    )
    mock_eveonline_client.async_get_industry_jobs.side_effect = EveOnlineError(
        "Service unavailable"
    )
    mock_eveonline_client.async_get_market_orders.side_effect = EveOnlineError(
        "Service unavailable"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # List endpoints return empty lists, count sensors should show 0
    state = hass.states.get("sensor.test_capsuleer_skill_queue")
    assert state is not None
    assert state.state == "0"

    # Industry jobs and market orders should also show 0
    state = hass.states.get("sensor.test_capsuleer_industry_jobs")
    assert state is not None
    assert state.state == "0"


async def test_setup_entry_implementation_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup when OAuth implementation is unavailable."""
    with patch(
        "homeassistant.components.eveonline.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError("not available"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_list_endpoint_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that auth errors on list endpoints propagate like optional endpoints."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_skill_queue.side_effect = (
        EveOnlineAuthenticationError("Token revoked")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_resolves_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the coordinator resolves IDs to names via the ESI API."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_location.return_value = CharacterLocation(
        solar_system_id=30000142
    )
    mock_eveonline_client.async_get_character_ship.return_value = CharacterShip(
        ship_type_id=587, ship_item_id=1, ship_name="My Rifter"
    )
    mock_eveonline_client.async_get_industry_jobs.return_value = [
        IndustryJob(
            job_id=1,
            activity_id=1,
            status="active",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 1, 2, tzinfo=UTC),
            blueprint_type_id=1137,
            output_location_id=60003760,
            runs=1,
            product_type_id=1138,
        ),
    ]
    mock_eveonline_client.async_get_market_orders.return_value = [
        MarketOrder(
            order_id=1,
            type_id=34,
            is_buy_order=False,
            price=10.0,
            volume_remain=100,
            volume_total=100,
            location_id=60003760,
            region_id=10000002,
            issued=datetime(2026, 1, 1, tzinfo=UTC),
            duration=90,
            range="region",
        ),
    ]
    mock_eveonline_client.async_resolve_names.return_value = [
        UniverseName(id=30000142, name="Jita", category="solar_system"),
        UniverseName(id=587, name="Rifter", category="inventory_type"),
        UniverseName(id=1137, name="Blueprint", category="inventory_type"),
        UniverseName(id=1138, name="Product", category="inventory_type"),
        UniverseName(id=34, name="Tritanium", category="inventory_type"),
    ]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Location should show resolved name
    state = hass.states.get("sensor.test_capsuleer_location")
    assert state is not None
    assert state.state == "Jita"

    # Ship should show resolved name
    state = hass.states.get("sensor.test_capsuleer_ship")
    assert state is not None
    assert state.state == "Rifter"


async def test_coordinator_resolve_names_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that a resolve_names failure degrades gracefully."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_location.return_value = CharacterLocation(
        solar_system_id=30000142
    )
    mock_eveonline_client.async_resolve_names.side_effect = EveOnlineError(
        "Resolve failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Location should fall back to numeric ID
    state = hass.states.get("sensor.test_capsuleer_location")
    assert state is not None
    assert state.state == "30000142"
