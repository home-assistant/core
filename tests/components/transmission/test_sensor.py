"""Transmission sensor platform tests."""
from homeassistant.components.transmission.const import (
    ORDER_BEST_RATIO_FIRST,
    ORDER_NEWEST_FIRST,
    ORDER_WORST_RATIO_FIRST,
)

from tests.components.transmission.conftest import (
    MOCK_LIMIT_TRUNCATED,
    MOCK_TORRENTS_BEST_TO_WORST,
    MOCK_TORRENTS_OLDEST_TO_NEWEST,
    mock_client_setup,
    setup_transmission,
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


async def test_status_seeding(hass):
    """Test the Transmission Status Seeding."""
    await mock_client_setup(hass, downloadSpeed=0)

    status = hass.states.get("sensor.transmission_status")
    assert status.state == "Seeding"


async def test_status_downloading(hass):
    """Test the Transmission Status Downloading."""
    await mock_client_setup(hass, uploadSpeed=0)

    status = hass.states.get("sensor.transmission_status")
    assert status.state == "Downloading"


async def test_status_idle(hass):
    """Test the Transmission Status Idle."""
    await mock_client_setup(hass, downloadSpeed=0, uploadSpeed=0)

    status = hass.states.get("sensor.transmission_status")
    assert status.state == "idle"


async def test_torrent_info(hass, torrent_info):
    """Test Torrent Info attributes old->new (default)."""
    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_OLDEST_TO_NEWEST


async def test_torrent_info_limit(hass):
    """Test Torrent Info attributes old->new truncated."""
    entry = setup_transmission(hass, limit=MOCK_LIMIT_TRUNCATED)
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_OLDEST_TO_NEWEST[
        :MOCK_LIMIT_TRUNCATED
    ]


async def test_torrent_info_order_recent(hass):
    """Test Torrent Info attributes new->old."""
    entry = setup_transmission(hass, order=ORDER_NEWEST_FIRST)
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_OLDEST_TO_NEWEST))
    assert [x["id"] for x in info.values()] == mocked


async def test_torrent_info_order_recent_limit(hass):
    """Test Torrent Info attributes new->old truncated."""
    entry = setup_transmission(
        hass, limit=MOCK_LIMIT_TRUNCATED, order=ORDER_NEWEST_FIRST
    )
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_OLDEST_TO_NEWEST))
    assert [x["id"] for x in info.values()] == mocked[:MOCK_LIMIT_TRUNCATED]


async def test_torrent_info_order_ratio(hass):
    """Test Torrent Info attributes best->worst ratio."""
    entry = setup_transmission(hass, order=ORDER_BEST_RATIO_FIRST)
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_BEST_TO_WORST


async def test_torrent_info_order_ratio_limit(hass):
    """Test Torrent Info attributes best->worst ratio truncated."""
    entry = setup_transmission(
        hass, limit=MOCK_LIMIT_TRUNCATED, order=ORDER_BEST_RATIO_FIRST
    )
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    assert [x["id"] for x in info.values()] == MOCK_TORRENTS_BEST_TO_WORST[
        :MOCK_LIMIT_TRUNCATED
    ]


async def test_torrent_info_order_ratio_worst(hass):
    """Test Torrent Info attributes worst->best ratio."""
    entry = setup_transmission(hass, order=ORDER_WORST_RATIO_FIRST)
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_BEST_TO_WORST))
    assert [x["id"] for x in info.values()] == mocked


async def test_torrent_info_order_ratio_worst_limit(hass):
    """Test Torrent Info attributes worst->best ratio truncated."""
    entry = setup_transmission(
        hass, limit=MOCK_LIMIT_TRUNCATED, order=ORDER_WORST_RATIO_FIRST
    )
    await mock_client_setup(hass, entry)

    total_torrents = hass.states.get("sensor.transmission_total_torrents")
    info = total_torrents.attributes["torrent_info"]
    mocked = list(reversed(MOCK_TORRENTS_BEST_TO_WORST))
    assert [x["id"] for x in info.values()] == mocked[:MOCK_LIMIT_TRUNCATED]
