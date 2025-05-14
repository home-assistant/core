"""The go2rtc component."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import shutil
from typing import TYPE_CHECKING

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError, ServerConnectionError
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components.default_config import DOMAIN as DEFAULT_CONFIG_DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntry
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    discovery_flow,
    issue_registry as ir,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.package import is_docker_env

from .const import (
    CONF_DEBUG_UI,
    DEBUG_UI_URL_MESSAGE,
    DOMAIN,
    HA_MANAGED_URL,
    RECOMMENDED_VERSION,
)
from .server import Server

if TYPE_CHECKING:
    from go2rtc_client import Go2RtcRestClient

    from homeassistant.components.camera import Camera

    from .client import Go2RtcClient

_LOGGER = logging.getLogger(__name__)

_SUPPORTED_STREAMS = frozenset(
    (
        "bubble",
        "dvrip",
        "expr",
        "ffmpeg",
        "gopro",
        "homekit",
        "http",
        "https",
        "httpx",
        "isapi",
        "ivideon",
        "kasa",
        "nest",
        "onvif",
        "roborock",
        "rtmp",
        "rtmps",
        "rtmpx",
        "rtsp",
        "rtsps",
        "rtspx",
        "tapo",
        "tcp",
        "webrtc",
        "webtorrent",
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Exclusive(CONF_URL, DOMAIN, DEBUG_UI_URL_MESSAGE): cv.url,
                vol.Exclusive(CONF_DEBUG_UI, DOMAIN, DEBUG_UI_URL_MESSAGE): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass(frozen=True)
class Go2RtcData:
    """Go2rtc data class."""

    url: str
    session: ClientSession
    rest_client: Go2RtcRestClient
    ha_clients: list[Go2RtcClient] = field(default_factory=list, init=False)


_DATA_GO2RTC: HassKey[str] = HassKey(DOMAIN)
_RETRYABLE_ERRORS = (ClientConnectionError, ServerConnectionError)
type Go2RtcConfigEntry = ConfigEntry[Go2RtcData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up WebRTC."""
    url: str | None = None
    if DOMAIN not in config and DEFAULT_CONFIG_DOMAIN not in config:
        await _remove_go2rtc_entries(hass)
        return True

    if not (configured_by_user := DOMAIN in config) or not (
        url := config[DOMAIN].get(CONF_URL)
    ):
        if not is_docker_env():
            if not configured_by_user:
                # Remove config entry if it exists
                await _remove_go2rtc_entries(hass)
                return True
            _LOGGER.warning("Go2rtc URL required in non-docker installs")
            return False
        if not (binary := await _get_binary(hass)):
            _LOGGER.error("Could not find go2rtc docker binary")
            return False

        # HA will manage the binary
        server = Server(
            hass, binary, enable_ui=config.get(DOMAIN, {}).get(CONF_DEBUG_UI, False)
        )
        try:
            await server.start()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not start go2rtc server", exc_info=True)
            return False

        async def on_stop(event: Event) -> None:
            await server.stop()

        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, on_stop)

        url = HA_MANAGED_URL

    hass.data[_DATA_GO2RTC] = url
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data={}
    )
    return True


async def _remove_go2rtc_entries(hass: HomeAssistant) -> None:
    """Remove go2rtc config entries, if any."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: Go2RtcConfigEntry) -> bool:
    """Set up go2rtc from a config entry."""

    # Keep import here so that we can import go2rtc integration without installing reqs
    # pylint: disable-next=import-outside-toplevel
    from go2rtc_client import Go2RtcRestClient

    # pylint: disable-next=import-outside-toplevel
    from go2rtc_client.exceptions import Go2RtcClientError, Go2RtcVersionError

    url = hass.data[_DATA_GO2RTC]
    session = async_get_clientsession(hass)
    client = Go2RtcRestClient(session, url)
    # Validate the server URL
    try:
        version = await client.validate_server_version()
        if version < AwesomeVersion(RECOMMENDED_VERSION):
            ir.async_create_issue(
                hass,
                DOMAIN,
                "recommended_version",
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="recommended_version",
                translation_placeholders={
                    "recommended_version": RECOMMENDED_VERSION,
                    "current_version": str(version),
                },
            )
    except Go2RtcClientError as err:
        if isinstance(err.__cause__, _RETRYABLE_ERRORS):
            raise ConfigEntryNotReady(
                f"Could not connect to go2rtc instance on {url}"
            ) from err
        _LOGGER.warning("Could not connect to go2rtc instance on %s (%s)", url, err)
        return False
    except Go2RtcVersionError as err:
        raise ConfigEntryNotReady(
            f"The go2rtc server version is not supported, {err}"
        ) from err
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not connect to go2rtc instance on %s (%s)", url, err)
        return False

    entry.runtime_data = Go2RtcData(url, session, client)

    async def inform_cameras() -> None:
        """Inform camera that go2rtc is available."""
        # To avoid circular import, we import the camera helper here
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.camera.helper import get_camera_entities

        await asyncio.gather(
            *(
                camera.async_create_go2rtc_client_if_needed()
                for camera in get_camera_entities(hass)
            )
        )

    hass.async_create_background_task(
        inform_cameras(), "go2rtc_inform_cameras", eager_start=False
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Go2RtcConfigEntry) -> bool:
    """Unload a go2rtc config entry."""
    for client in entry.runtime_data.ha_clients:
        await client.teardown()
    entry.runtime_data.ha_clients.clear()
    return True


async def _get_binary(hass: HomeAssistant) -> str | None:
    """Return the binary path if found."""
    return await hass.async_add_executor_job(shutil.which, "go2rtc")


async def create_go2rtc_client(
    camera: Camera, client_remove_fn: Callable[[], None]
) -> Go2RtcClient | None:
    """Create a Go2rtc client."""
    hass = camera.hass
    entries: list[Go2RtcConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return None

    stream_source = await camera.stream_source()
    if not stream_source or stream_source.partition(":")[0] not in _SUPPORTED_STREAMS:
        # Not supported by go2rtc
        return None

    # Keep import here so that we can import stream integration without installing reqs
    # pylint: disable-next=import-outside-toplevel
    from .client import Go2RtcClient

    return Go2RtcClient(hass, entries[0].runtime_data, camera, client_remove_fn)
