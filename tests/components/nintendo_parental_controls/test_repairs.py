"""Test repairs for Nintendo Parental Controls."""

from unittest.mock import AsyncMock, patch

from pynintendoparental.exceptions import NoDevicesFoundException

from homeassistant.components.nintendo_parental_controls.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry


async def test_no_devices_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test number platform."""
    mock_nintendo_client.update.side_effect = NoDevicesFoundException(None)
    # We don't need to create entities for this test
    with patch(
        "homeassistant.components.nintendo_parental_controls._PLATFORMS",
        [],
    ):
        await setup_integration(hass, mock_config_entry)

    assert (
        DOMAIN,
        "no_devices_found",
    ) in issue_registry.issues
