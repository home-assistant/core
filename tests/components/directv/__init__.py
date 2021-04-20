"""Tests for the DirecTV component."""
from homeassistant.components.directv.const import CONF_RECEIVER_ID, DOMAIN
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION
from homeassistant.const import (
    CONF_HOST,
    CONTENT_TYPE_JSON,
    HTTP_FORBIDDEN,
    HTTP_INTERNAL_SERVER_ERROR,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

HOST = "127.0.0.1"
RECEIVER_ID = "028877455858"
SSDP_LOCATION = "http://127.0.0.1/"
UPNP_SERIAL = "RID-028877455858"

MOCK_CONFIG = {DOMAIN: [{CONF_HOST: HOST}]}
MOCK_SSDP_DISCOVERY_INFO = {ATTR_SSDP_LOCATION: SSDP_LOCATION}
MOCK_USER_INPUT = {CONF_HOST: HOST}


def mock_connection(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the DirecTV connection for Home Assistant."""
    aioclient_mock.get(
        f"http://{HOST}:8080/info/getVersion",
        text=load_fixture("directv/info-get-version.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/info/getLocations",
        text=load_fixture("directv/info-get-locations.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/info/mode",
        params={"clientAddr": "B01234567890"},
        text=load_fixture("directv/info-mode-standby.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/info/mode",
        params={"clientAddr": "9XXXXXXXXXX9"},
        status=HTTP_INTERNAL_SERVER_ERROR,
        text=load_fixture("directv/info-mode-error.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/info/mode",
        text=load_fixture("directv/info-mode.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/remote/processKey",
        text=load_fixture("directv/remote-process-key.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/tv/tune",
        text=load_fixture("directv/tv-tune.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/tv/getTuned",
        params={"clientAddr": "2CA17D1CD30X"},
        text=load_fixture("directv/tv-get-tuned.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/tv/getTuned",
        params={"clientAddr": "A01234567890"},
        text=load_fixture("directv/tv-get-tuned-music.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/tv/getTuned",
        params={"clientAddr": "C01234567890"},
        status=HTTP_FORBIDDEN,
        text=load_fixture("directv/tv-get-tuned-restricted.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}:8080/tv/getTuned",
        text=load_fixture("directv/tv-get-tuned-movie.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


async def setup_integration(
    hass: HomeAssistantType,
    aioclient_mock: AiohttpClientMocker,
    skip_entry_setup: bool = False,
    setup_error: bool = False,
) -> MockConfigEntry:
    """Set up the DirecTV integration in Home Assistant."""
    if setup_error:
        aioclient_mock.get(
            f"http://{HOST}:8080/info/getVersion", status=HTTP_INTERNAL_SERVER_ERROR
        )
    else:
        mock_connection(aioclient_mock)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=RECEIVER_ID,
        data={CONF_HOST: HOST, CONF_RECEIVER_ID: RECEIVER_ID},
    )

    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
