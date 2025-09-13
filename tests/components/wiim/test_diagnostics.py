"""pytest diagnostics.py."""

from unittest.mock import MagicMock

import pytest
from wiim.consts import InputMode, LoopMode, PlayingStatus
from wiim.wiim_device import WiimDevice

from homeassistant.components.wiim.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_get_config_entry_diagnostics(
    mock_hass: HomeAssistant, mock_config_entry: MagicMock, mock_wiim_device: WiimDevice
) -> None:
    """Test async_get_config_entry_diagnostics returns correct data."""
    mock_config_entry.runtime_data = mock_wiim_device

    mock_wiim_device._udn = "uuid:test-diagnostics-udn"
    mock_wiim_device._name = "Test Diagnostics Device"
    mock_wiim_device._model_name = "WiiM Mini"
    mock_wiim_device._manufacturer = "Linkplay Tech"
    mock_wiim_device._available = True

    mock_wiim_device.volume = 60
    mock_wiim_device.is_muted = False
    mock_wiim_device.playing_status = PlayingStatus.PLAYING
    mock_wiim_device.current_track_info = {
        "title": "Song Title",
        "artist": "Artist Name",
        "album": "Album Name",
        "albumArtURI": "http://example.com/album_art.jpg",
        "uri": "http://stream.url/song.mp3",
        "duration": "00:04:15",
    }
    mock_wiim_device.current_position = 30
    mock_wiim_device.current_track_duration = 255
    mock_wiim_device.play_mode = InputMode.WIFI.display_name  # type: ignore[attr-defined]
    mock_wiim_device.loop_mode = LoopMode.SHUFFLE_ENABLE_REPEAT_ALL
    mock_wiim_device.equalizer_mode = MagicMock(value="Rock")
    mock_wiim_device.next_track_uri = "http://next.track.com/next.mp3"

    mock_upnp_device = MagicMock()
    mock_upnp_device.device_type = "urn:schemas-upnp-org:device:MediaRenderer:1"
    mock_upnp_device.presentation_url = "http://192.168.1.200:8080/presentation"
    mock_upnp_device.device_url = "http://192.168.1.200:49152/description.xml"
    mock_upnp_device.services = {
        "urn:upnp-org:serviceId:AVTransport": MagicMock(service_id="AVTransport"),
        "urn:upnp-org:serviceId:RenderingControl": MagicMock(
            service_id="RenderingControl"
        ),
        "urn:upnp-org:serviceId:PlayQueue": MagicMock(service_id="PlayQueue"),
    }
    mock_wiim_device.upnp_device = mock_upnp_device

    mock_av_transport_state = MagicMock()
    mock_av_transport_state.name = "AVTState"
    mock_av_transport_state.value = "Playing"
    mock_wiim_device.av_transport = MagicMock(
        state_variables={"AVTState": mock_av_transport_state}
    )

    mock_rendering_control_state = MagicMock()
    mock_rendering_control_state.name = "RCState"
    mock_rendering_control_state.value = "Volume=50"
    mock_wiim_device.rendering_control = MagicMock(
        state_variables={"RCState": mock_rendering_control_state}
    )

    mock_play_queue_state = MagicMock()
    mock_play_queue_state.name = "PQState"
    mock_play_queue_state.value = "QueueData"
    mock_wiim_device.play_queue_service = MagicMock(
        state_variables={"PQState": mock_play_queue_state}
    )

    diagnostics_data = await async_get_config_entry_diagnostics(
        mock_hass, mock_config_entry
    )

    assert isinstance(diagnostics_data, dict)

    assert diagnostics_data["entry_data"] == dict(mock_config_entry.data)
    assert diagnostics_data["device_udn"] == mock_wiim_device.udn
    assert diagnostics_data["device_name"] == mock_wiim_device.name
    assert diagnostics_data["model_name"] == mock_wiim_device.model_name
    assert diagnostics_data["manufacturer"] == mock_wiim_device._manufacturer
    assert diagnostics_data["firmware_version"] == mock_wiim_device.firmware_version
    assert diagnostics_data["ip_address"] == mock_wiim_device.ip_address
    assert diagnostics_data["http_api_url"] == mock_wiim_device.http_api_url
    assert diagnostics_data["is_available_sdk"] == mock_wiim_device.available

    assert (
        diagnostics_data["upnp_device_info"]["device_type"]
        == mock_upnp_device.device_type
    )
    assert (
        diagnostics_data["upnp_device_info"]["presentation_url"]
        == mock_upnp_device.presentation_url
    )
    assert (
        diagnostics_data["upnp_device_info"]["device_url_desc_xml"]
        == mock_upnp_device.device_url
    )
    assert diagnostics_data["upnp_device_info"]["services"] == [
        "AVTransport",
        "RenderingControl",
        "PlayQueue",
    ]

    media_state = diagnostics_data["current_media_player_state"]
    assert media_state["volume"] == mock_wiim_device.volume
    assert media_state["is_muted"] == mock_wiim_device.is_muted
    assert media_state["playing_status"] == mock_wiim_device.playing_status.value
    assert media_state["current_track_info"] == mock_wiim_device.current_track_info
    assert media_state["play_mode"] == mock_wiim_device.play_mode
    assert media_state["loop_mode"] == mock_wiim_device.loop_mode.value
    assert media_state["equalizer_mode"] == mock_wiim_device.equalizer_mode.value
    assert media_state["current_position_sec"] == mock_wiim_device.current_position
    assert (
        media_state["current_track_duration_sec"]
        == mock_wiim_device.current_track_duration
    )
    assert media_state["next_track_uri"] == mock_wiim_device.next_track_uri

    assert (
        diagnostics_data["upnp_av_transport_state"]["AVTState"]
        == mock_av_transport_state.value
    )
    assert (
        diagnostics_data["upnp_rendering_control_state"]["RCState"]
        == mock_rendering_control_state.value
    )
    assert (
        diagnostics_data["upnp_play_queue_state"]["PQState"]
        == mock_play_queue_state.value
    )


@pytest.mark.asyncio
async def test_async_get_diagnostics_no_upnp_device(
    mock_hass: HomeAssistant, mock_config_entry: MagicMock, mock_wiim_device: WiimDevice
) -> None:
    """Test diagnostics when UPnP device is not fully initialized."""
    mock_config_entry.runtime_data = mock_wiim_device
    mock_wiim_device.av_transport = None
    mock_wiim_device.rendering_control = None
    mock_wiim_device.play_queue_service = None

    diagnostics_data = await async_get_config_entry_diagnostics(
        mock_hass, mock_config_entry
    )

    assert "upnp_av_transport_state" not in diagnostics_data
    assert "upnp_rendering_control_state" not in diagnostics_data
    assert "upnp_play_queue_state" not in diagnostics_data

    assert diagnostics_data["device_udn"] == mock_wiim_device.udn
    assert "current_media_player_state" in diagnostics_data
    assert (
        diagnostics_data["current_media_player_state"]["loop_mode"]
        == mock_wiim_device.loop_mode.value
    )
