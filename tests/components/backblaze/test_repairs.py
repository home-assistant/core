"""Test Backblaze repairs."""

from unittest.mock import AsyncMock, Mock

from b2sdk.v2.exception import (
    B2Error,
    NonExistentBucket,
    RestrictedBucket,
    Unauthorized,
)

from homeassistant.components.backblaze.repairs import (
    async_check_for_repair_issues,
    async_create_fix_flow,
)
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_repair_issue_unauthorized(hass: HomeAssistant) -> None:
    """Test that unauthorized errors don't create repair issues (handled by reauth)."""
    entry = MockConfigEntry(domain="backblaze", data={"bucket": "test"})
    bucket = Mock()
    entry.runtime_data = bucket

    # Mock executor job to raise Unauthorized
    hass.async_add_executor_job = AsyncMock(
        side_effect=Unauthorized("test", "auth_failed")
    )

    await async_check_for_repair_issues(hass, entry)

    # Should not create issue for Unauthorized (handled by reauth flow)
    issues = ir.async_get(hass).issues
    assert len(issues) == 0


async def test_repair_issue_restricted_bucket(hass: HomeAssistant) -> None:
    """Test repair issue creation for restricted bucket error."""
    entry = MockConfigEntry(domain="backblaze", data={"bucket": "test"})
    bucket = Mock()
    entry.runtime_data = bucket

    # Mock executor job to raise RestrictedBucket
    hass.async_add_executor_job = AsyncMock(side_effect=RestrictedBucket("test"))

    await async_check_for_repair_issues(hass, entry)

    # Check that issue was created
    issues = ir.async_get(hass).issues
    assert len(issues) == 1


async def test_repair_issue_nonexistent_bucket(hass: HomeAssistant) -> None:
    """Test repair issue creation for nonexistent bucket error."""
    entry = MockConfigEntry(domain="backblaze", data={"bucket": "test"})
    bucket = Mock()
    entry.runtime_data = bucket

    # Mock executor job to raise NonExistentBucket
    hass.async_add_executor_job = AsyncMock(side_effect=NonExistentBucket("test"))

    await async_check_for_repair_issues(hass, entry)

    # Check that issue was created
    issues = ir.async_get(hass).issues
    assert len(issues) == 1


async def test_repair_issue_b2_error(hass: HomeAssistant) -> None:
    """Test repair issue with B2Error (covers debug logging)."""
    entry = MockConfigEntry(domain="backblaze", data={"bucket": "test"})
    bucket = Mock()
    entry.runtime_data = bucket

    # Mock executor job to raise B2Error
    hass.async_add_executor_job = AsyncMock(side_effect=B2Error("test"))

    await async_check_for_repair_issues(hass, entry)

    # Should not create issue for generic B2Error, just log


async def test_async_create_fix_flow(hass: HomeAssistant) -> None:
    """Test creating repair fix flow."""
    flow = await async_create_fix_flow(hass, "test_issue", None)
    assert isinstance(flow, ConfirmRepairFlow)
