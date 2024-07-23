"""Test repairs handling for Sonos."""

from unittest.mock import Mock

from soco import SoCo

from homeassistant.components.sonos.const import (
    DOMAIN,
    SCAN_INTERVAL,
    SUB_FAIL_ISSUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry
from homeassistant.util import dt as dt_util

from .conftest import SonosMockEvent, SonosMockSubscribe

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_subscription_repair_issues(
    hass: HomeAssistant, config_entry: MockConfigEntry, soco: SoCo, zgs_discovery
) -> None:
    """Test repair issues handling for failed subscriptions."""
    issue_registry = async_get_issue_registry(hass)

    subscription: SonosMockSubscribe = soco.zoneGroupTopology.subscribe.return_value
    subscription.event_listener = Mock(address=("192.168.4.2", 1400))

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Ensure an issue is registered on subscription failure
    sub_callback = await subscription.wait_for_callback_to_be_set()
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)

    # Ensure the issue still exists after reload
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)

    # Ensure the issue has been removed after a successful subscription callback
    variables = {"ZoneGroupState": zgs_discovery}
    event = SonosMockEvent(soco, soco.zoneGroupTopology, variables)
    sub_callback(event)
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue(DOMAIN, SUB_FAIL_ISSUE_ID)
    await hass.async_block_till_done(wait_background_tasks=True)
