"""Test Deluge sensor.py methods."""

from homeassistant.components.deluge.const import DelugeSensorType
from homeassistant.components.deluge.sensor import get_state

from . import GET_TORRENT_STATUS_RESPONSE


def test_get_state() -> None:
    """Tests get_state() with different keys."""

    download_result = get_state(
        GET_TORRENT_STATUS_RESPONSE, DelugeSensorType.DOWNLOAD_SPEED_SENSOR
    )
    assert download_result == 0.1  # round(98.5 / 1024, 2)

    upload_result = get_state(
        GET_TORRENT_STATUS_RESPONSE, DelugeSensorType.UPLOAD_SPEED_SENSOR
    )
    assert upload_result == 3.4  # round(3462.0 / 1024, 1)

    protocol_upload_result = get_state(
        GET_TORRENT_STATUS_RESPONSE,
        DelugeSensorType.PROTOCOL_TRAFFIC_UPLOAD_SPEED_SENSOR,
    )
    assert protocol_upload_result == 7.6  # round(7818.0 / 1024, 1)

    protocol_download_result = get_state(
        GET_TORRENT_STATUS_RESPONSE,
        DelugeSensorType.PROTOCOL_TRAFFIC_DOWNLOAD_SPEED_SENSOR,
    )
    assert protocol_download_result == 2.6  # round(2658.0/1024, 1)
