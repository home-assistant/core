"""Sensor tests for the YouTube integration."""
from datetime import timedelta
from unittest.mock import patch

from google.auth.exceptions import RefreshError
import pytest
from syrupy import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.youtube import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import MockService
from .conftest import TOKEN, ComponentSetup

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


async def test_sensor_updating(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test updating sensor."""
    await setup_integration()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state
    assert state.attributes["video_id"] == "wysukDrMdqU"

    with patch(
        "homeassistant.components.youtube.api.build",
        return_value=MockService(
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
        == "https://i.ytimg.com/vi/hleLlcHwQLM/sddefault.jpg"
    )
    assert state.attributes["video_id"] == "hleLlcHwQLM"


async def test_sensor_reauth_trigger(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test reauth is triggered after a refresh error."""
    await setup_integration()

    with patch(TOKEN, side_effect=RefreshError):
        future = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH


@pytest.mark.parametrize(
    ("fixture", "url", "has_entity_picture"),
    [
        ("standard", "https://i.ytimg.com/vi/wysukDrMdqU/sddefault.jpg", True),
        ("high", "https://i.ytimg.com/vi/wysukDrMdqU/hqdefault.jpg", True),
        ("medium", "https://i.ytimg.com/vi/wysukDrMdqU/mqdefault.jpg", True),
        ("default", "https://i.ytimg.com/vi/wysukDrMdqU/default.jpg", True),
        ("none", None, False),
    ],
)
async def test_thumbnail(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    fixture: str,
    url: str | None,
    has_entity_picture: bool,
) -> None:
    """Test if right thumbnail is selected."""
    await setup_integration()

    with patch(
        "homeassistant.components.youtube.api.build",
        return_value=MockService(
            playlist_items_fixture=f"youtube/thumbnail/{fixture}.json"
        ),
    ):
        future = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state
    assert ("entity_picture" in state.attributes) is has_entity_picture
    assert state.attributes.get("entity_picture") == url
