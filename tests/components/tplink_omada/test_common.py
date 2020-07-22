"""Test for TP-Link Omada common.py file."""
from homeassistant.components.tplink_omada.common import OmadaData
from homeassistant.components.tplink_omada.const import (
    CONF_DNSRESOLVE,
    CONF_SSLVERIFY,
    CONTROLLER_PATH,
    DOMAIN,
    LOGIN_PATH,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

HOST = "https://127.0.0.1:8443"
NAME = "fakeomada"
USERNAME = "admin"
PASSWORD = "password"
UNIQUE_ID = "fakeomada"
ACTUAL_HOST = "https://127.0.0.1"
TIMEOUT = 60
DNSRESOLVE = False
SSLVERIFY = False


class HistoryMock:
    """Mock http client history."""

    headers = {"location": ACTUAL_HOST}


def mock_connection(aioclient_mock: AiohttpClientMocker, host: str = HOST,) -> None:
    """Mock the Omada connection."""
    # roku_url = f"http://{host}:8060"
    token = "myfaketoken"
    aioclient_mock.get(
        f"{host}",
        text="",
        history=[HistoryMock()],
        headers={"Content-Type": "application/json"},
    )

    fixtures = [
        (LOGIN_PATH, "tplink_omada/login.json", {"ajax": ""}),
        (CONTROLLER_PATH, "tplink_omada/about.json", {"aboutInfo": "", "token": token}),
        (
            CONTROLLER_PATH,
            "tplink_omada/global_stats.json",
            {"globalStat": "", "token": token},
        ),
        (
            CONTROLLER_PATH,
            "tplink_omada/ssid_stats.json",
            {"ssidStatsStore": "", "token": token},
        ),
        (
            CONTROLLER_PATH,
            "tplink_omada/ap_stats.json",
            {"apsStore": "", "token": token},
        ),
        (
            CONTROLLER_PATH,
            "tplink_omada/clients.json",
            {"userStore": "", "token": token},
        ),
        (
            CONTROLLER_PATH,
            "tplink_omada/ssid_settings.json",
            {"wlBasicSsidGridS": "", "token": token},
        ),
        # (CONTROLLER_PATH, "tplink_omada/ssid_edit_settings_post.json"),
    ]

    for fixture in fixtures:
        aioclient_mock.post(
            f"{host}{CONTROLLER_PATH}",
            params=fixture[2],
            text=load_fixture(fixture[1]),
            headers={"Content-Type": "application/json"},
        )


async def prepare_test(hass, aioclient_mock):
    """Load all mocks."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_TIMEOUT: TIMEOUT,
            CONF_DNSRESOLVE: DNSRESOLVE,
            CONF_SSLVERIFY: SSLVERIFY,
        },
    )
    mock_connection(aioclient_mock=aioclient_mock,)
    return OmadaData(hass, entry)


async def test_async_update(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker,
):
    """Test data fetching."""
    omada_data = await prepare_test(hass, aioclient_mock)
    await omada_data.async_update()
    # Login
    assert omada_data.available is True
    assert omada_data._base_url == ACTUAL_HOST  # pylint: disable=protected-access
    assert omada_data._token == "myfaketoken"  # pylint: disable=protected-access
    # About
    assert omada_data.version == "3.2.10"
    # Global stats
    assert omada_data.data["activeUser"] == 23
    # SSID stats
    assert omada_data.ssid_stats == "1.0"
    # AP stats
    assert omada_data.access_points_stats == "1.0"
    # AP settings
    assert omada_data.access_points_settings == "1.0"
    # SSID attrs
    assert omada_data.ssid_attrs == "1.0"
