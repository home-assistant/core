"""Tests for the IPP integration."""
import aiohttp
from pyipp import IPPConnectionUpgradeRequired, IPPError

from homeassistant.components import zeroconf
from homeassistant.components.ipp.const import CONF_BASE_PATH, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_UUID,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, get_fixture_path
from tests.test_util.aiohttp import AiohttpClientMocker

ATTR_HOSTNAME = "hostname"
ATTR_PROPERTIES = "properties"

HOST = "192.168.1.31"
PORT = 631
BASE_PATH = "/ipp/print"

IPP_ZEROCONF_SERVICE_TYPE = "_ipp._tcp.local."
IPPS_ZEROCONF_SERVICE_TYPE = "_ipps._tcp.local."

ZEROCONF_NAME = "EPSON XP-6000 Series"
ZEROCONF_HOST = HOST
ZEROCONF_HOSTNAME = "EPSON123456.local."
ZEROCONF_PORT = PORT
ZEROCONF_RP = "ipp/print"

MOCK_USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
    CONF_BASE_PATH: BASE_PATH,
}

MOCK_ZEROCONF_IPP_SERVICE_INFO = zeroconf.ZeroconfServiceInfo(
    type=IPP_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{IPP_ZEROCONF_SERVICE_TYPE}",
    host=ZEROCONF_HOST,
    addresses=[ZEROCONF_HOST],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"rp": ZEROCONF_RP},
)

MOCK_ZEROCONF_IPPS_SERVICE_INFO = zeroconf.ZeroconfServiceInfo(
    type=IPPS_ZEROCONF_SERVICE_TYPE,
    name=f"{ZEROCONF_NAME}.{IPPS_ZEROCONF_SERVICE_TYPE}",
    host=ZEROCONF_HOST,
    addresses=[ZEROCONF_HOST],
    hostname=ZEROCONF_HOSTNAME,
    port=ZEROCONF_PORT,
    properties={"rp": ZEROCONF_RP},
)


def load_fixture_binary(filename):
    """Load a binary fixture."""
    return get_fixture_path(filename, "ipp").read_bytes()


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: int = PORT,
    ssl: bool = False,
    base_path: str = BASE_PATH,
    conn_error: bool = False,
    conn_upgrade_error: bool = False,
    ipp_error: bool = False,
    no_unique_id: bool = False,
    parse_error: bool = False,
    version_not_supported: bool = False,
):
    """Mock the IPP connection."""
    scheme = "https" if ssl else "http"
    ipp_url = f"{scheme}://{host}:{port}"

    if ipp_error:
        aioclient_mock.post(f"{ipp_url}{base_path}", exc=IPPError)
        return

    if conn_error:
        aioclient_mock.post(f"{ipp_url}{base_path}", exc=aiohttp.ClientError)
        return

    if conn_upgrade_error:
        aioclient_mock.post(f"{ipp_url}{base_path}", exc=IPPConnectionUpgradeRequired)
        return

    fixture = "get-printer-attributes.bin"
    if no_unique_id:
        fixture = "get-printer-attributes-success-nodata.bin"
    elif version_not_supported:
        fixture = "get-printer-attributes-error-0x0503.bin"

    if parse_error:
        content = "BAD"
    else:
        content = load_fixture_binary(fixture)

    aioclient_mock.post(
        f"{ipp_url}{base_path}",
        content=content,
        headers={"Content-Type": "application/ipp"},
    )


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    skip_setup: bool = False,
    host: str = HOST,
    port: int = PORT,
    ssl: bool = False,
    base_path: str = BASE_PATH,
    uuid: str = "cfe92100-67c4-11d4-a45f-f8d027761251",
    unique_id: str = "cfe92100-67c4-11d4-a45f-f8d027761251",
    conn_error: bool = False,
) -> MockConfigEntry:
    """Set up the IPP integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: ssl,
            CONF_VERIFY_SSL: True,
            CONF_BASE_PATH: base_path,
            CONF_UUID: uuid,
        },
    )

    entry.add_to_hass(hass)

    mock_connection(
        aioclient_mock,
        host=host,
        port=port,
        ssl=ssl,
        base_path=base_path,
        conn_error=conn_error,
    )

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
