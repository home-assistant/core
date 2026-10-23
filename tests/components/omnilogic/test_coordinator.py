"""Tests for the Omnilogic coordinator."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from omnilogic import OmniLogic, OmniLogicException

from homeassistant.components.omnilogic.const import DOMAIN, SCAN_INTERVAL
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def _get_telemetry_data(api: OmniLogic) -> list[dict[str, Any]]:
    """Behave like omnilogic: only log in again when there is no token."""
    if api.token is None:
        api.token = "new-token"
    if api.token == "rejected-token":
        raise OmniLogicException("Error converting Hayward data to JSON.")
    return []


async def test_rejected_token_logs_in_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the next update logs in again after Hayward rejects the token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    entry.add_to_hass(hass)

    with (
        patch.object(OmniLogic, "connect", return_value=True),
        patch.object(
            OmniLogic,
            "get_telemetry_data",
            autospec=True,
            side_effect=_get_telemetry_data,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data
        assert coordinator.last_update_success
        # Empty telemetry creates no entities, and without a listener the
        # coordinator does not poll.
        coordinator.async_add_listener(lambda: None)

        coordinator.api.token = "rejected-token"
        freezer.tick(timedelta(seconds=SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert not coordinator.last_update_success

        freezer.tick(timedelta(seconds=SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert coordinator.last_update_success
