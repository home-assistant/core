"""Test repairs handling for Sonos."""

from unittest.mock import Mock, patch

from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from soco import SoCo

from homeassistant.components.sonos.const import (
    DOMAIN,
    SCAN_INTERVAL,
    SUB_FAIL_ISSUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import SonosMockEvent, SonosMockSubscribe


async def test_subscription_repair_issues(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    soco: SoCo,
    zgs_discovery,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issues handling for failed subscriptions."""
    subscription: SonosMockSubscribe = soco.zoneGroupTopology.subscribe.return_value
    subscription.event_listener = Mock(address=("192.168.4.2", 1400))

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Ensure an issue is registered on subscription failure
    sub_callback = await subscription.wait_for_callback_to_be_set()
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)
    issue = issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)
    assert issue
    assert issue.config_entry_id == config_entry.entry_id

    # Ensure the issue still exists after reload
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)

    # Ensure the issue has been removed after a successful subscription callback
    variables = {"ZoneGroupState": zgs_discovery}
    event = SonosMockEvent(soco, soco.zoneGroupTopology, variables)
    sub_callback(event)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)


async def test_subscription_failure_after_unload_creates_no_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    soco: SoCo,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a subscription timeout firing after unload creates no issue."""
    subscription: SonosMockSubscribe = soco.zoneGroupTopology.subscribe.return_value
    subscription.event_listener = Mock(address=("192.168.4.2", 1400))

    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.sonos.async_call_later") as mock_call_later:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await subscription.wait_for_callback_to_be_set()
    subscription_failed = mock_call_later.call_args.args[2]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await subscription_failed(dt_util.utcnow())

    assert not issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)
