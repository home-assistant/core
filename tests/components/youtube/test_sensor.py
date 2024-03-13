"""Sensor tests for the YouTube integration."""

from datetime import timedelta
from unittest.mock import patch

from syrupy import SnapshotAssertion
from youtubeaio.types import UnauthorizedError, YouTubeBackendError

from homeassistant import config_entries
from homeassistant.components.youtube.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MockYouTube
from .conftest import ComponentSetup

from tests.common import async_fire_time_changed


async def test_sensor(
    hass: HomeAssistant, snapshot: SnapshotAssertion, setup_integration: ComponentSetup
) -> None:
    """Test sensor."""
    await setup_integration()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state == snapshot

    state = hass.states.get("sensor.google_for_developers_subscribers")
    assert state == snapshot


async def test_sensor_without_uploaded_video(
    hass: HomeAssistant, snapshot: SnapshotAssertion, setup_integration: ComponentSetup
) -> None:
    """Test sensor when there is no video on the channel."""
    await setup_integration()

    with patch(
        "homeassistant.components.youtube.api.AsyncConfigEntryAuth.get_resource",
        return_value=MockYouTube(
            playlist_items_fixture="youtube/get_no_playlist_items.json"
        ),
    ):
        future = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state == snapshot

    state = hass.states.get("sensor.google_for_developers_subscribers")
    assert state == snapshot


async def test_sensor_updating(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test updating sensor."""
    await setup_integration()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state
    assert state.attributes["video_id"] == "wysukDrMdqU"

    with patch(
        "homeassistant.components.youtube.api.AsyncConfigEntryAuth.get_resource",
        return_value=MockYouTube(
            playlist_items_fixture="youtube/get_playlist_items_2.json"
        ),
    ):
        future = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state
    assert state.name == "Google for Developers Latest upload"
    assert state.state == "Google I/O 2023 Developer Keynote in 5 minutes"
    assert (
        state.attributes["entity_picture"]
        == "https://i.ytimg.com/vi/hleLlcHwQLM/maxresdefault.jpg"
    )
    assert state.attributes["video_id"] == "hleLlcHwQLM"


async def test_sensor_reauth_trigger(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test reauth is triggered after a refresh error."""
    mock = await setup_integration()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state.state == "What's new in Google Home in less than 1 minute"

    state = hass.states.get("sensor.google_for_developers_subscribers")
    assert state.state == "2290000"

    mock.set_thrown_exception(UnauthorizedError())
    future = dt_util.utcnow() + timedelta(minutes=15)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH


async def test_sensor_unavailable(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test update failed."""
    mock = await setup_integration()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state.state == "What's new in Google Home in less than 1 minute"

    state = hass.states.get("sensor.google_for_developers_subscribers")
    assert state.state == "2290000"

    mock.set_thrown_exception(YouTubeBackendError())
    future = dt_util.utcnow() + timedelta(minutes=15)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state.state == "unavailable"

    state = hass.states.get("sensor.google_for_developers_subscribers")
    assert state.state == "unavailable"
