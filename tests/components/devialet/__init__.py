"""Tests for the Devialet integration."""

from ipaddress import ip_address

from aiohttp import ClientError as ServerTimeoutError
from devialet.const import UrlSuffix

from homeassistant.components.devialet.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

NAME = "Livingroom"
SERIAL = "L00P00000AB11"
HOST = "127.0.0.1"
CONF_INPUT = {CONF_HOST: HOST}

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

MOCK_CONFIG = {DOMAIN: [{CONF_HOST: HOST}]}
MOCK_USER_INPUT = {CONF_HOST: HOST}
MOCK_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    hostname="PhantomISilver-L00P00000AB11.local.",
    type="_devialet-http._tcp.",
    name="Livingroom",
    port=80,
    properties={
        "_raw": {
            "firmwareFamily": "DOS",
            "firmwareVersion": "2.16.1.49152",
            "ipControlVersion": "1",
            "manufacturer": "Devialet",
            "model": "Phantom I Silver",
            "path": "/ipcontrol/v1",
            "serialNumber": "L00P00000AB11",
        },
        "firmwareFamily": "DOS",
        "firmwareVersion": "2.16.1.49152",
        "ipControlVersion": "1",
        "manufacturer": "Devialet",
        "model": "Phantom I Silver",
        "path": "/ipcontrol/v1",
        "serialNumber": "L00P00000AB11",
    },
)


def mock_unavailable(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Devialet connection for Home Assistant."""
    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_GENERAL_INFO}", exc=ServerTimeoutError
    )


def mock_idle(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Devialet connection for Home Assistant."""
    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_GENERAL_INFO}",
        text=load_fixture("general_info.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_CURRENT_SOURCE}",
        exc=ServerTimeoutError,
    )


def mock_playing(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the Devialet connection for Home Assistant."""
    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_GENERAL_INFO}",
        text=load_fixture("general_info.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_CURRENT_SOURCE}",
        text=load_fixture("source_state.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_SOURCES}",
        text=load_fixture("sources.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_VOLUME}",
        text=load_fixture("volume.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_NIGHT_MODE}",
        text=load_fixture("night_mode.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_EQUALIZER}",
        text=load_fixture("equalizer.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://{HOST}{UrlSuffix.GET_CURRENT_POSITION}",
        text=load_fixture("current_position.json", DOMAIN),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_entry_setup: bool = False,
    state: str = "playing",
    serial: str = SERIAL,
) -> MockConfigEntry:
    """Set up the Devialet integration in Home Assistant."""

    if state == "playing":
        mock_playing(aioclient_mock)
    elif state == "unavailable":
        mock_unavailable(aioclient_mock)
    elif state == "idle":
        mock_idle(aioclient_mock)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=serial,
        data=CONF_DATA,
    )

    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
