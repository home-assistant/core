"""Test repairs for Husqvarna Automower."""

from unittest.mock import AsyncMock

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry


async def test_invalid_mower_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an issue is created for an invalid mower."""
    mower_name = "Garden mower"
    issue_id = f"invalid_mower_{mower_name}"
    mock_automower_client.invalid_mowers = [mower_name]

    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.translation_key == "invalid_mower"
    assert issue.translation_placeholders == {
        "mower_name": mower_name,
    }
