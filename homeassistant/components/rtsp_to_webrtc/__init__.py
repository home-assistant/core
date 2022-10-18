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

import logging

import async_timeout
from rtsp_to_webrtc.client import get_adaptive_client
from rtsp_to_webrtc.exceptions import ClientError, ResponseError
from rtsp_to_webrtc.interface import WebRTCClientInterface
import voluptuous as vol

from homeassistant.components import camera, websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rtsp_to_webrtc"
DATA_SERVER_URL = "server_url"
DATA_UNSUB = "unsub"
TIMEOUT = 10
CONF_STUN_SERVER = "stun_server"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RTSPtoWebRTC from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client: WebRTCClientInterface
    try:
        async with async_timeout.timeout(TIMEOUT):
            client = await get_adaptive_client(
                async_get_clientsession(hass), entry.data[DATA_SERVER_URL]
            )
    except ResponseError as err:
        raise ConfigEntryNotReady from err
    except (TimeoutError, ClientError) as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][CONF_STUN_SERVER] = entry.options.get(CONF_STUN_SERVER, "")

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
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    websocket_api.async_register_command(hass, ws_get_settings)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data:
        del hass.data[DOMAIN]
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    if hass.data[DOMAIN][CONF_STUN_SERVER] != entry.options.get(CONF_STUN_SERVER, ""):
        await hass.config_entries.async_reload(entry.entry_id)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "rtsp_to_webrtc/get_settings",
    }
)
@callback
def ws_get_settings(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle the websocket command."""
    connection.send_result(
        msg["id"],
        {CONF_STUN_SERVER: hass.data.get(DOMAIN, {}).get(CONF_STUN_SERVER, "")},
    )
