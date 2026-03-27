"""Test the Eve Online integration setup."""

import base64
from datetime import UTC, datetime
import json
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

from homeassistant.components.eveonline.const import DOMAIN, SCOPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
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
    """Test that auth errors on optional endpoints trigger reauth.

    Unlike generic EveOnlineError, EveOnlineAuthenticationError is translated
    to ConfigEntryAuthFailed in _fetch_optional, triggering a reauth flow.
    """
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = (
        EveOnlineAuthenticationError("Token revoked")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Auth errors become ConfigEntryAuthFailed → SETUP_ERROR + reauth
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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
    """Test that auth errors on list endpoints trigger reauth."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_skill_queue.side_effect = (
        EveOnlineAuthenticationError("Token revoked")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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


def _make_jwt_with_scopes(
    character_id: int, character_name: str, scopes: list[str]
) -> str:
    """Create a fake Eve SSO JWT token with specific scopes."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=")
    payload_data = {
        "sub": f"CHARACTER:EVE:{character_id}",
        "name": character_name,
        "scp": scopes,
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=")
    signature = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=")
    return f"{header.decode()}.{payload.decode()}.{signature.decode()}"


async def test_missing_scopes_creates_repair_issue(
    hass: HomeAssistant,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that missing scopes create a repair issue."""
    partial_scopes = SCOPES[:3]
    fake_jwt = _make_jwt_with_scopes(12345678, "Test Capsuleer", partial_scopes)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Capsuleer",
        unique_id="12345678",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": fake_jwt,
                "refresh_token": "mock-refresh-token",
                "expires_in": 1200,
                "token_type": "Bearer",
            },
            "character_id": 12345678,
            "character_name": "Test Capsuleer",
        },
    )
    entry.add_to_hass(hass)
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(DOMAIN, f"missing_scopes_{entry.entry_id}")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.is_fixable is True


async def test_all_scopes_no_repair_issue(
    hass: HomeAssistant,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that all scopes present does not create a repair issue."""
    fake_jwt = _make_jwt_with_scopes(12345678, "Test Capsuleer", SCOPES)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Capsuleer",
        unique_id="12345678",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": fake_jwt,
                "refresh_token": "mock-refresh-token",
                "expires_in": 1200,
                "token_type": "Bearer",
            },
            "character_id": 12345678,
            "character_name": "Test Capsuleer",
        },
    )
    entry.add_to_hass(hass)
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(DOMAIN, f"missing_scopes_{entry.entry_id}")
    assert issue is None


async def test_unparseable_token_no_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a non-JWT token does not create a repair issue."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(
        DOMAIN, f"missing_scopes_{mock_config_entry.entry_id}"
    )
    assert issue is None


def test_get_token_scopes_single_scope() -> None:
    """Test _get_token_scopes with a single scope string (not a list)."""
    from homeassistant.components.eveonline import _get_token_scopes

    # Eve SSO returns a single string when only one scope is granted.
    payload_data = {
        "sub": "CHARACTER:EVE:123",
        "name": "Test",
        "scp": "esi-location.read_location.v1",
    }
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(
        b"="
    )
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=")
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=")
    token = f"{header.decode()}.{payload.decode()}.{sig.decode()}"

    result = _get_token_scopes({"access_token": token})
    assert result == {"esi-location.read_location.v1"}


def test_get_token_scopes_invalid_base64() -> None:
    """Test _get_token_scopes with invalid base64 in the token."""
    from homeassistant.components.eveonline import _get_token_scopes

    result = _get_token_scopes({"access_token": "header.!!!bad!!!.sig"})
    assert result == set()
