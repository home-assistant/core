"""Test the Eve Online repair flows."""

import base64
import json
from unittest.mock import AsyncMock

from homeassistant.components.eveonline.const import DOMAIN, SCOPES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import mock_server_status

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


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


async def test_missing_scopes_repair_flow(
    hass: HomeAssistant,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the repair flow triggers reauth for missing scopes."""
    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)

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

    issue_id = f"missing_scopes_{entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is True

    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Verify reauth flow was started.
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)
