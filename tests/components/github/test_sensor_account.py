"""Test GitHub account sensors."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.github.const import FALLBACK_UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_account_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    github_client: AsyncMock,
) -> None:
    """Test account sensors."""
    # Setup manually to control title before setup
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, title="Mock User")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Entity ID: sensor.account_mock_user_notifications
    state = hass.states.get("sensor.account_mock_user_notifications")
    assert state
    assert state.state == "0"  # conftest sets []

    state = hass.states.get("sensor.account_mock_user_assigned_issues")
    assert state
    assert state.state == "10"  # conftest sets 10

    state = hass.states.get("sensor.account_mock_user_assigned_pull_requests")
    assert state
    assert state.state == "10"  # reused search_mock

    state = hass.states.get("sensor.account_mock_user_review_requests")
    assert state
    assert state.state == "10"  # reused search_mock

    # Update data
    notifications_mock = MagicMock()
    notifications_mock.data = [
        {
            "subject": {"title": "T1", "type": "Issue", "url": "U1"},
            "repository": {"full_name": "R1", "html_url": "H1"},
        },
        {
            "subject": {"title": "T2", "type": "PR", "url": "U2"},
            "repository": {"full_name": "R2", "html_url": "H2"},
        },
        {
            "subject": {"title": "T3", "type": "Issue", "url": "U3"},
            "repository": {"full_name": "R3", "html_url": "H3"},
        },
    ]  # 3 notifications

    search_mock = MagicMock()
    search_mock.data = {
        "total_count": 42,
        "items": [
            {
                "title": "S1",
                "number": 1,
                "html_url": "SU1",
                "repository_url": "https://api.github.com/repos/o/r",
            }
        ],
    }

    async def generic_side_effect(endpoint, **kwargs):
        if "notifications" in endpoint:
            return notifications_mock
        return search_mock

    github_client.generic.side_effect = generic_side_effect
    # github_client.search_issues.return_value = search_mock # Removed

    # Fire update
    async_fire_time_changed(hass, dt_util.utcnow() + FALLBACK_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.account_mock_user_notifications")
    assert state.state == "3"

    state = hass.states.get("sensor.account_mock_user_assigned_issues")
    assert state.state == "42"
