"""RTSPtoWebRTC integration with an external RTSPToWebRTC Server.

WebRTC uses a direct communication from the client (e.g. a web browser) to a
camera device. Home Assistant acts as the signal path for initial set up,
passing through the client offer and returning a camera answer, then the client
and camera communicate directly.

However, not all cameras natively support WebRTC. This integration is a shim
for camera devices that support RTSP streams only, relying on an external
server RTSPToWebRTC that is a proxy. Home Assistant does not participate in
the offer/answer SDP protocol, other than as a signal path pass through.

Other integrations may use this integration with these steps:
- Check if this integration is loaded
- Call is_suported_stream_source for compatibility
- Call async_offer_for_stream_source to get back an answer for a client offer
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from aiortc.rtcrtpsender import RTCRtpSender
import async_timeout
from rtsp_to_webrtc.client import get_adaptive_client
from rtsp_to_webrtc.exceptions import ClientError, ResponseError
from rtsp_to_webrtc.interface import WebRTCClientInterface
import voluptuous as vol

from homeassistant.components import camera, websocket_api
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rtsp_to_webrtc"
DATA_SERVER_URL = "server_url"
DATA_UNSUB = "unsub"
TIMEOUT = 10
CONF_STUN_SERVER = "stun_server"
LISTENER = "listener"


async def _async_setup_external_server(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the external RTSPToWebRTC server."""
    client: WebRTCClientInterface
    server_url: str = entry.options[DATA_SERVER_URL]
    try:
        async with async_timeout.timeout(TIMEOUT):
            client = await get_adaptive_client(
                async_get_clientsession(hass), server_url
            )
    except ResponseError as err:
        raise ConfigEntryNotReady from err
    except (TimeoutError, ClientError) as err:
        raise ConfigEntryNotReady from err

    async def async_offer_for_stream_source(
        stream_source: str,
        offer_sdp: str,
        stream_id: str,
    ) -> str:
        """Handle the signal path for a WebRTC stream.

        This signal path is used to route the offer created by the client to the
        proxy server that translates a stream to WebRTC. The communication for
        the stream itself happens directly between the client and proxy.
        """
        try:
            async with async_timeout.timeout(TIMEOUT):
                return await client.offer_stream_id(stream_id, offer_sdp, stream_source)
        except TimeoutError as err:
            raise HomeAssistantError("Timeout talking to RTSPtoWebRTC server") from err
        except ClientError as err:
            raise HomeAssistantError(str(err)) from err

    entry.async_on_unload(
        camera.async_register_rtsp_to_web_rtc_provider(
            hass, DOMAIN, async_offer_for_stream_source
        )
    )


async def _async_setup_internal_server(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the internal RTSPToWebRTC server."""
    peer_connections: set[RTCPeerConnection] = set()

    async def _async_offer_for_stream_source(
        stream_source: str,
        offer_sdp: str,
    ) -> str:
        """Handle the signal path for a WebRTC stream."""
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        peer_connection = RTCPeerConnection()
        peer_connections.add(peer_connection)

        @peer_connection.on("connectionstatechange")  # type: ignore[misc]
        async def _on_connection_state_change() -> None:
            _LOGGER.debug("Connection state is %s", peer_connection.connectionState)
            if peer_connection.connectionState == "failed":
                await peer_connection.close()
                peer_connections.discard(peer_connection)

        # open media source
        _LOGGER.debug("Starting stream %s", stream_source)
        player = MediaPlayer(stream_source, decode=False)
        with contextlib.suppress(AttributeError):
            peer_connection.addTrack(player.audio)

        video_sender = peer_connection.addTrack(player.video)

        # force H264 codec
        forced_codec = "video/H264"
        kind = forced_codec.split("/", maxsplit=1)[0]
        codecs = RTCRtpSender.getCapabilities(kind).codecs
        transceiver = next(
            t for t in peer_connection.getTransceivers() if t.sender == video_sender
        )
        transceiver.setCodecPreferences(
            [codec for codec in codecs if codec.mimeType == forced_codec]
        )
        await peer_connection.setRemoteDescription(offer)
        answer = await peer_connection.createAnswer()
        await peer_connection.setLocalDescription(answer)
        sdp_answer: str = peer_connection.localDescription.sdp
        _LOGGER.debug("answer=%s", sdp_answer)
        return sdp_answer

    async def async_offer_for_stream_source(
        stream_source: str,
        offer_sdp: str,
        stream_id: str,
    ) -> str:
        """Handle the signal path for a WebRTC stream."""
        try:
            return await _async_offer_for_stream_source(stream_source, offer_sdp)
        except Exception as err:
            _LOGGER.exception("Error handling offer for stream %s", stream_id)
            raise HomeAssistantError(str(err)) from err

    async def on_shutdown(event: Event) -> None:
        # close peer connections
        await asyncio.gather(
            *[peer_connection.close() for peer_connection in peer_connections]
        )
        peer_connections.clear()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_shutdown)

    entry.async_on_unload(
        camera.async_register_rtsp_to_web_rtc_provider(
            hass, DOMAIN, async_offer_for_stream_source
        )
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track the state of the sun."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )
    return True


class ReloadListener:
    """Listen for config entry reloads."""

    def __init__(self, original_options: dict[str, Any]) -> None:
        """Initialize the listener."""
        self.original_options = original_options

    async def async_reload_entry(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Reload config entry when options change."""
        if self.original_options != entry.options:
            await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RTSPtoWebRTC from a config entry."""
    if DATA_SERVER_URL in entry.data:
        # Server is optional now, but was required in the past
        hass.config_entries.async_update_entry(
            entry,
            data={},
            options=entry.options | {DATA_SERVER_URL: entry.data[DATA_SERVER_URL]},
        )

    if entry.options.get(DATA_SERVER_URL):
        await _async_setup_external_server(hass, entry)
    else:
        await _async_setup_internal_server(hass, entry)

    listener = ReloadListener(dict(entry.options))
    hass.data.setdefault(DOMAIN, {}).update(
        {
            CONF_STUN_SERVER: entry.options.get(CONF_STUN_SERVER, ""),
            LISTENER: listener,
        }
    )

    entry.async_on_unload(entry.add_update_listener(listener.async_reload_entry))

    websocket_api.async_register_command(hass, ws_get_settings)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data:
        del hass.data[DOMAIN]
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rtsp_to_webrtc/get_settings",
    }
)
@callback
def ws_get_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle the websocket command."""
    connection.send_result(
        msg["id"],
        {CONF_STUN_SERVER: hass.data.get(DOMAIN, {}).get(CONF_STUN_SERVER, "")},
    )
