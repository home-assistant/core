"""Test loading of the Tibber config entry."""

from unittest.mock import MagicMock

from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_repair_flow(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_tibber_setup: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test unloading the entry."""

    # Test legacy notify service
    service = "tibber"
    service_data = {"message": "The message", "title": "A title"}
    await hass.services.async_call("notify", service, service_data, blocking=True)
    calls: MagicMock = mock_tibber_setup.send_notification

    calls.assert_called_once_with(message="The message", title="A title")
    calls.reset_mock()

    http_client = await hass_client()
    # Assert the issue is present
    assert issue_registry.async_get_issue(
        domain="notify",
        issue_id=f"migrate_notify_tibber_{service}",
    )
    assert len(issue_registry.issues) == 1

    data = await start_repair_fix_flow(
        http_client, "notify", f"migrate_notify_tibber_{service}"
    )

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Simulate the users confirmed the repair flow
    data = await process_repair_fix_flow(http_client, flow_id)
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(
        domain="notify",
        issue_id=f"migrate_notify_tibber_{service}",
    )
    assert len(issue_registry.issues) == 0
