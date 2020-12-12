"""Transmission sensor platform tests."""

from tests.components.transmission.conftest import (
    MOCK_TORRENTS_BEST_TO_WORST,
    MOCK_TORRENTS_OLDEST_TO_NEWEST,
)


async def test_sensors(hass, torrent_info):
    """Test the Transmission sensor states."""
    down_speed = hass.states.get("sensor.transmission_down_speed")
    assert down_speed.state == "0.05"

    up_speed = hass.states.get("sensor.transmission_up_speed")
    assert up_speed.state == "0.03"

    status = hass.states.get("sensor.transmission_status")
    assert status.state == "Up/Down"

    active_torrents = hass.states.get("sensor.transmission_active_torrents")
    assert active_torrents.state == "5"

    paused_torrents = hass.states.get("sensor.transmission_paused_torrents")
    assert paused_torrents.state == "0"

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    assert total_torrents.state == "5"

    completed_torrents = hass.states.get("sensor.transmission_completed_torrents")
    assert completed_torrents.state == "0"

    started_torrents = hass.states.get("sensor.transmission_started_torrents")
    assert started_torrents.state == "5"


async def test_status_seeding(hass, status_seeding):
    """Test the Transmission Status sensor."""
    status = hass.states.get("sensor.transmission_status")
    assert status.state == "Seeding"


async def test_status_downloading(hass, status_downloading):
    """Test the Transmission Status sensor."""
    status = hass.states.get("sensor.transmission_status")
    assert status.state == "Downloading"


async def test_status_idle(hass, status_idle):
    """Test the Transmission Status sensor."""
    status = hass.states.get("sensor.transmission_status")
    assert status.state == "idle"


async def test_torrent_info(hass, torrent_info):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_OLDEST_TO_NEWEST


async def test_torrent_info_limit(hass, torrent_limit):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_OLDEST_TO_NEWEST[:2]


async def test_torrent_info_order_recent(hass, torrent_order_recent):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_OLDEST_TO_NEWEST))
    assert [x["id"] for x in info.values()] == mocked


async def test_torrent_info_order_recent_limit(hass, torrent_order_recent_limit):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_OLDEST_TO_NEWEST))
    assert [x["id"] for x in info.values()] == mocked[:2]


async def test_torrent_info_order_ratio(hass, torrent_order_ratio):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_BEST_TO_WORST


async def test_torrent_info_order_ratio_limit(hass, torrent_order_ratio_limit):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_BEST_TO_WORST[:2]


async def test_torrent_info_order_ratio_worst(hass, torrent_order_ratio_worst):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_BEST_TO_WORST))
    assert [x["id"] for x in info.values()] == mocked


async def test_torrent_info_order_ratio_worst_limit(
    hass, torrent_order_ratio_worst_limit
):
    """Test the Transmission Torrent Info attributes."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_BEST_TO_WORST))
    assert [x["id"] for x in info.values()] == mocked[:2]
