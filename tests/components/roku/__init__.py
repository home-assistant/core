"""Tests for the Roku component."""
import re
from socket import gaierror as SocketGIAError

from homeassistant.components.roku.const import DOMAIN
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
)
from homeassistant.const import CONF_HOST, CONF_ID, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

NAME = "Roku 3"
NAME_ROKUTV = '58" Onn Roku TV'

HOST = "192.168.1.160"
SSDP_LOCATION = "http://192.168.1.160/"
UPNP_FRIENDLY_NAME = "My Roku 3"
UPNP_SERIAL = "1GU48T017973"

MOCK_SSDP_DISCOVERY_INFO = {
    ATTR_SSDP_LOCATION: SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME: UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL: UPNP_SERIAL,
}

HOMEKIT_HOST = "192.168.1.161"

MOCK_HOMEKIT_DISCOVERY_INFO = {
    CONF_NAME: "onn._hap._tcp.local.",
    CONF_HOST: HOMEKIT_HOST,
    "properties": {
        CONF_ID: "2d:97:da:ee:dc:99",
    },
}


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    device: str = "roku3",
    app: str = "roku",
    host: str = HOST,
    power: bool = True,
    media_state: str = "close",
    error: bool = False,
    server_error: bool = False,
) -> None:
    """Mock the Roku connection."""
    roku_url = f"http://{host}:8060"

    if error:
        mock_connection_error(
            aioclient_mock=aioclient_mock, device=device, app=app, host=host
        )
        return

    if server_error:
        mock_connection_server_error(
            aioclient_mock=aioclient_mock, device=device, app=app, host=host
        )
        return

    info_fixture = f"roku/{device}-device-info.xml"
    if not power:
        info_fixture = f"roku/{device}-device-info-power-off.xml"

    aioclient_mock.get(
        f"{roku_url}/query/device-info",
        text=load_fixture(info_fixture),
        headers={"Content-Type": "text/xml"},
    )

    apps_fixture = "roku/apps.xml"
    if device == "rokutv":
        apps_fixture = "roku/apps-tv.xml"

    aioclient_mock.get(
        f"{roku_url}/query/apps",
        text=load_fixture(apps_fixture),
        headers={"Content-Type": "text/xml"},
    )

    aioclient_mock.get(
        f"{roku_url}/query/active-app",
        text=load_fixture(f"roku/active-app-{app}.xml"),
        headers={"Content-Type": "text/xml"},
    )

    aioclient_mock.get(
        f"{roku_url}/query/tv-active-channel",
        text=load_fixture("roku/rokutv-tv-active-channel.xml"),
        headers={"Content-Type": "text/xml"},
    )

    aioclient_mock.get(
        f"{roku_url}/query/tv-channels",
        text=load_fixture("roku/rokutv-tv-channels.xml"),
        headers={"Content-Type": "text/xml"},
    )

    aioclient_mock.get(
        f"{roku_url}/query/media-player",
        text=load_fixture(f"roku/media-player-{media_state}.xml"),
        headers={"Content-Type": "text/xml"},
    )

    aioclient_mock.post(
        re.compile(f"{roku_url}/keypress/.*"),
        text="OK",
    )

    aioclient_mock.post(
        re.compile(f"{roku_url}/launch/.*"),
        text="OK",
    )

    aioclient_mock.post(f"{roku_url}/search", text="OK")


def mock_connection_error(
    aioclient_mock: AiohttpClientMocker,
    device: str = "roku3",
    app: str = "roku",
    host: str = HOST,
) -> None:
    """Mock the Roku connection error."""
    roku_url = f"http://{host}:8060"

    aioclient_mock.get(f"{roku_url}/query/device-info", exc=SocketGIAError)
    aioclient_mock.get(f"{roku_url}/query/apps", exc=SocketGIAError)
    aioclient_mock.get(f"{roku_url}/query/active-app", exc=SocketGIAError)
    aioclient_mock.get(f"{roku_url}/query/tv-active-channel", exc=SocketGIAError)
    aioclient_mock.get(f"{roku_url}/query/tv-channels", exc=SocketGIAError)

    aioclient_mock.post(re.compile(f"{roku_url}/keypress/.*"), exc=SocketGIAError)
    aioclient_mock.post(re.compile(f"{roku_url}/launch/.*"), exc=SocketGIAError)
    aioclient_mock.post(f"{roku_url}/search", exc=SocketGIAError)


def mock_connection_server_error(
    aioclient_mock: AiohttpClientMocker,
    device: str = "roku3",
    app: str = "roku",
    host: str = HOST,
) -> None:
    """Mock the Roku server error."""
    roku_url = f"http://{host}:8060"

    aioclient_mock.get(f"{roku_url}/query/device-info", status=500)
    aioclient_mock.get(f"{roku_url}/query/apps", status=500)
    aioclient_mock.get(f"{roku_url}/query/active-app", status=500)
    aioclient_mock.get(f"{roku_url}/query/tv-active-channel", status=500)
    aioclient_mock.get(f"{roku_url}/query/tv-channels", status=500)

    aioclient_mock.post(re.compile(f"{roku_url}/keypress/.*"), status=500)
    aioclient_mock.post(re.compile(f"{roku_url}/launch/.*"), status=500)
    aioclient_mock.post(f"{roku_url}/search", status=500)


async def setup_integration(
    hass: HomeAssistantType,
    aioclient_mock: AiohttpClientMocker,
    device: str = "roku3",
    app: str = "roku",
    host: str = HOST,
    unique_id: str = UPNP_SERIAL,
    error: bool = False,
    power: bool = True,
    media_state: str = "close",
    server_error: bool = False,
    skip_entry_setup: bool = False,
) -> MockConfigEntry:
    """Set up the Roku integration in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data={CONF_HOST: host})

    entry.add_to_hass(hass)

    if not skip_entry_setup:
        mock_connection(
            aioclient_mock,
            device,
            app=app,
            host=host,
            error=error,
            power=power,
            media_state=media_state,
            server_error=server_error,
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
