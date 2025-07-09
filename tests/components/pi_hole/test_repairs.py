"""Test pi_hole component."""

from datetime import timedelta
from unittest.mock import AsyncMock

from hole.exceptions import HoleConnectionError, HoleError
import pytest

import homeassistant
from homeassistant.components import pi_hole
from homeassistant.components.pi_hole.const import VERSION_6_RESPONSE_TO_5_ERROR
from homeassistant.const import CONF_API_VERSION, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from . import CONFIG_DATA_DEFAULTS, ZERO_DATA, _create_mocked_hole, _patch_init_hole

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_change_api_5_to_6(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Tests a user with an API version 5 config entry that is updated to API version 6."""
    mocked_hole = _create_mocked_hole(api_version=5)

    # setu up a valid API version 5 config entry
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN,
        data={**CONFIG_DATA_DEFAULTS, CONF_API_VERSION: 5},
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

        assert mocked_hole.instances[-1].data == ZERO_DATA
        # Change the mock's state after setup
        mocked_hole.instances[-1].hole_version = 6
        mocked_hole.instances[-1].api_token = "wrong_token"

        # Patch the method on the coordinator's api reference directly
        pihole_data = entry.runtime_data
        assert pihole_data.api == mocked_hole.instances[-1]
        pihole_data.api.get_data = AsyncMock(
            side_effect=lambda: setattr(
                pihole_data.api,
                "data",
                {"error": VERSION_6_RESPONSE_TO_5_ERROR, "took": 0.0001430511474609375},
            )
        )

        # Now trigger the update
        with pytest.raises(homeassistant.exceptions.ConfigEntryAuthFailed):
            await pihole_data.coordinator.update_method()
        assert pihole_data.api.data == {
            "error": VERSION_6_RESPONSE_TO_5_ERROR,
            "took": 0.0001430511474609375,
        }

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
        await hass.async_block_till_done()
        # ensure a re-auth flow is created
        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert flows[0]["step_id"] == "reauth_confirm"
        assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_app_password_changing(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Tests a user with an API version 5 config entry that is updated to API version 6."""
    mocked_hole = _create_mocked_hole(
        api_version=6, has_data=True, incorrect_app_password=False
    )
    entry = MockConfigEntry(domain=pi_hole.DOMAIN, data={**CONFIG_DATA_DEFAULTS})
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

    state = hass.states.get("sensor.pi_hole_ads_blocked")
    assert state is not None
    assert state.name == "Pi-Hole Ads blocked"
    assert state.state == "0"

    # Test app password changing
    async def fail_auth():
        """Set mocked data to bad_data."""
        raise HoleError("Authentication failed: Invalid password")

    mocked_hole.instances[-1].get_data = AsyncMock(side_effect=fail_auth)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["entry_id"] == entry.entry_id

    # Test app password changing
    async def fail_fetch():
        """Set mocked data to bad_data."""
        raise HoleConnectionError("Cannot fetch data from Pi-hole: 200")

    mocked_hole.instances[-1].get_data = AsyncMock(side_effect=fail_fetch)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()


async def test_app_failed_fetch(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Tests a user with an API version 5 config entry that is updated to API version 6."""
    mocked_hole = _create_mocked_hole(
        api_version=6, has_data=True, incorrect_app_password=False
    )
    entry = MockConfigEntry(domain=pi_hole.DOMAIN, data={**CONFIG_DATA_DEFAULTS})
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

    state = hass.states.get("sensor.pi_hole_ads_blocked")
    assert state.state == "0"

    # Test fetch failing changing
    async def fail_fetch():
        """Set mocked data to bad_data."""
        raise HoleConnectionError("Cannot fetch data from Pi-hole: 200")

    mocked_hole.instances[-1].get_data = AsyncMock(side_effect=fail_fetch)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.pi_hole_ads_blocked")
    assert state.state == STATE_UNAVAILABLE
