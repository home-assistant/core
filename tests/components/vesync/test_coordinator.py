"""Tests for the coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import requests_mock

from homeassistant.components.vesync.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import mock_air_purifier_400s_update_response, mock_devices_response

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test Vesync coordinator data update.

    This test sets up a single device `Air Purifier 400s` and then updates it via the coordinator.
    """

    config_data = {CONF_PASSWORD: "username", CONF_USERNAME: "password"}
    config_entry = MockConfigEntry(
        data=config_data,
        domain=DOMAIN,
        unique_id="vesync_unique_id_1",
        entry_id="1",
    )

    mock_devices_response(requests_mock, "Air Purifier 400s")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # Air Purifier 400s should generate 1 fan and 3 sensor entities
    assert hass.states.get("fan.air_purifier_400s").state != STATE_UNAVAILABLE
    assert (
        hass.states.get("sensor.air_purifier_400s_filter_lifetime").state
        != STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.air_purifier_400s_air_quality").state
        != STATE_UNAVAILABLE
    )
    assert hass.states.get("sensor.air_purifier_400s_pm2_5").state != STATE_UNAVAILABLE

    # Update the mock to supply air_quality=15
    mock_air_purifier_400s_update_response(requests_mock)

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.air_purifier_400s_air_quality").state == 15
