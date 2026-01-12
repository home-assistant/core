"""Test Backblaze B2 repairs."""

from unittest.mock import Mock, patch

from b2sdk.v2.exception import (
    B2Error,
    NonExistentBucket,
    RestrictedBucket,
    Unauthorized,
)
import pytest

from homeassistant.components.backblaze_b2.repairs import (
    async_check_for_repair_issues,
    async_create_fix_flow,
)
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.fixture
def mock_entry():
    """Create a mock config entry with runtime data."""
    entry = MockConfigEntry(domain="backblaze_b2", data={"bucket": "test"})
    entry.runtime_data = Mock()
    return entry


@pytest.mark.parametrize(
    ("exception", "expected_issues"),
    [
        (Unauthorized("test", "auth_failed"), 0),  # Handled by reauth flow
        (RestrictedBucket("test"), 1),  # Creates repair issue
        (NonExistentBucket("test"), 1),  # Creates repair issue
        (B2Error("test"), 0),  # Just logs, no issue
    ],
)
async def test_repair_issue_creation(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    exception: Exception,
    expected_issues: int,
) -> None:
    """Test repair issue creation for different exception types."""
    with patch.object(hass, "async_add_executor_job", side_effect=exception):
        await async_check_for_repair_issues(hass, mock_entry)

    issues = ir.async_get(hass).issues
    assert len(issues) == expected_issues


async def test_async_create_fix_flow(hass: HomeAssistant) -> None:
    """Test creating repair fix flow."""
    flow = await async_create_fix_flow(hass, "test_issue", None)
    assert isinstance(flow, ConfirmRepairFlow)
