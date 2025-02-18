"""The tests for the evohome coordinator."""

from __future__ import annotations

from unittest.mock import patch

import evohomeasync2 as ec2
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.evohome.const import DOMAIN
from homeassistant.components.evohome.coordinator import EvoDataUpdateCoordinator
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import async_fire_time_changed


@pytest.mark.parametrize("install", ["minimal"])
async def test_setup_platform(
    hass: HomeAssistant,
    config: dict[str, str],
    evohome: ec2.EvohomeClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and their states after setup of evohome."""

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator: EvoDataUpdateCoordinator = config_entry.runtime_data["coordinator"]

    update_interval = coordinator.update_interval
    assert update_interval is not None  # mypy hint

    # confirm initial state after coordinator.async_first_refresh()...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE

    with patch(
        "homeassistant.components.evohome.coordinator.EvoDataUpdateCoordinator._async_update_data",
        side_effect=UpdateFailed,
    ):
        freezer.tick(update_interval)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # confirm appropriate response to loss of state...
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state == STATE_UNAVAILABLE

    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # if coordinator is working, the state will be restored
    state = hass.states.get("climate.my_home")
    assert state is not None and state.state != STATE_UNAVAILABLE
