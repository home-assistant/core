"""Tests for Plex sensors."""
from homeassistant.const import STATE_UNAVAILABLE

from .helpers import trigger_plex_update, wait_for_debouncer

LIBRARY_UPDATE_PAYLOAD = {"StatusNotification": [{"title": "Library scan complete"}]}


async def test_library_sensor_values(
    hass,
    setup_plex_server,
    mock_websocket,
    requests_mock,
    library_tvshows_size,
    library_tvshows_size_episodes,
    library_tvshows_size_seasons,
):
    """Test the library sensors."""
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=2",
        text=library_tvshows_size,
    )
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=3",
        text=library_tvshows_size_seasons,
    )
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=4",
        text=library_tvshows_size_episodes,
    )

    await setup_plex_server()
    await wait_for_debouncer(hass)

    activity_sensor = hass.states.get("sensor.plex_plex_server_1")
    assert activity_sensor.state == "1"

    library_tv_sensor = hass.states.get("sensor.plex_server_1_library_tv_shows")
    assert library_tv_sensor.state == "10"
    assert library_tv_sensor.attributes["seasons"] == 1
    assert library_tv_sensor.attributes["shows"] == 1

    # Handle library deletion
    requests_mock.get(
        "/library/sections/2/all?includeCollections=0&type=2", status_code=404
    )
    trigger_plex_update(
        mock_websocket, msgtype="status", payload=LIBRARY_UPDATE_PAYLOAD
    )
    await hass.async_block_till_done()

    library_tv_sensor = hass.states.get("sensor.plex_server_1_library_tv_shows")
    assert library_tv_sensor.state == STATE_UNAVAILABLE
