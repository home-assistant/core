"""Tests for the Samsung ExLink coordinator."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from samsung_exlink import SamsungTVError

from homeassistant.components.samsung_exlink.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import MockSamsungTV


@pytest.mark.usefixtures("init_components")
async def test_polling_failure_and_recovery(
    hass: HomeAssistant,
    mock_samsung_tv: MockSamsungTV,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test both entities become unavailable on poll failure and recover."""
    coordinator = mock_config_entry.runtime_data
    media_player = hass.states.get("media_player.samsung_tv")
    remote = hass.states.get("remote.samsung_tv")
    assert media_player is not None
    assert remote is not None
    assert media_player.state == STATE_ON
    assert remote.state == STATE_ON

    mock_samsung_tv.refresh.side_effect = SamsungTVError("refresh failed")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "update_failed"
    media_player = hass.states.get("media_player.samsung_tv")
    remote = hass.states.get("remote.samsung_tv")
    assert media_player is not None
    assert remote is not None
    assert media_player.state == STATE_UNAVAILABLE
    assert remote.state == STATE_UNAVAILABLE

    mock_samsung_tv.refresh.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    media_player = hass.states.get("media_player.samsung_tv")
    remote = hass.states.get("remote.samsung_tv")
    assert media_player is not None
    assert remote is not None
    assert media_player.state == STATE_ON
    assert remote.state == STATE_ON
    assert mock_samsung_tv.refresh.await_count == 3
