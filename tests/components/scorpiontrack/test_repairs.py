"""Test repairs for inaccessible ScorpionTrack shares."""

from dataclasses import replace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import (
    CONF_SHARE_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ScorpionTrackInvalidTokenError("Rejected"), id="rejected"),
        pytest.param(ScorpionTrackShareUnavailableError("Expired"), id="unavailable"),
    ],
)
async def test_setup_error_creates_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
    exception: Exception,
) -> None:
    """An inaccessible share needs attention until a reload succeeds."""
    mock_scorpiontrack_client.async_get_share.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"share_unavailable_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.translation_key == "share_unavailable"
    assert issue.translation_placeholders == {"name": mock_config_entry.title}
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_scorpiontrack_client.async_get_share.assert_awaited_once_with()

    mock_scorpiontrack_client.async_get_share.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not issue_registry.issues
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_scorpiontrack_client.async_get_share.await_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ScorpionTrackInvalidTokenError("Rejected"), id="rejected"),
        pytest.param(ScorpionTrackShareUnavailableError("Expired"), id="unavailable"),
    ],
)
async def test_repair_clears_on_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
    exception: Exception,
) -> None:
    """Repeated failures create one issue, which a successful update clears."""
    await setup_integration(hass, mock_config_entry)
    mock_scorpiontrack_client.async_get_share.side_effect = exception

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1
    assert hass.states.get("device_tracker.ab12_cde").state == STATE_UNAVAILABLE

    mock_scorpiontrack_client.async_get_share.side_effect = None
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not issue_registry.issues
    assert hass.states.get("device_tracker.ab12_cde").state != STATE_UNAVAILABLE
    assert mock_scorpiontrack_client.async_get_share.await_count == 4


async def test_connection_failure_does_not_create_repair(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A temporary connection or response error needs no share replacement."""
    await setup_integration(hass, mock_config_entry)
    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackConnectionError("Invalid response")
    )
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not issue_registry.issues
    assert hass.states.get("device_tracker.ab12_cde").state == STATE_UNAVAILABLE


async def test_setup_connection_failure_does_not_create_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A temporary setup failure remains retryable without a repair."""
    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackConnectionError("Connection failed")
    )
    await setup_integration(hass, mock_config_entry)

    assert not issue_registry.issues
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(None, id="loaded"),
        pytest.param(ScorpionTrackShareUnavailableError("Expired"), id="setup-error"),
    ],
)
async def test_removal_clears_only_own_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scorpiontrack_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
    exception: Exception | None,
) -> None:
    """Removing an entry clears its issue without requiring runtime data."""
    mock_scorpiontrack_client.async_get_share.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    own_issue_id = f"share_unavailable_{mock_config_entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        own_issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="share_unavailable",
        translation_placeholders={"name": mock_config_entry.title},
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        "share_unavailable_other",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="share_unavailable",
        translation_placeholders={"name": "Another share"},
    )

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, own_issue_id) is None
    assert issue_registry.async_get_issue(DOMAIN, "share_unavailable_other") is not None


async def test_reconfiguration_clears_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Reconfiguring the same share clears its repair after a successful reload."""
    mock_scorpiontrack_client.async_get_share.side_effect = (
        ScorpionTrackInvalidTokenError("Rejected")
    )
    await setup_integration(hass, mock_config_entry)
    issue_id = f"share_unavailable_{mock_config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    mock_scorpiontrack_client.async_get_share.side_effect = None
    mock_scorpiontrack_client.async_get_share.return_value = replace(
        mock_share, token="updated-token"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
        data={CONF_SHARE_TOKEN: "updated-token"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_SHARE_TOKEN: "updated-token"}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert mock_scorpiontrack_client.async_get_share.await_count == 3
