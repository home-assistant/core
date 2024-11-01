"""Configure pytest for Netgear LTE tests."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError
import pytest

from homeassistant.components.netgear_lte.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

HOST = "192.168.5.1"
PASSWORD = "password"

CONF_DATA = {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}


@pytest.fixture
def cannot_connect(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock cannot connect error."""
    aioclient_mock.get(f"http://{HOST}/model.json", exc=ClientError)
    aioclient_mock.post(f"http://{HOST}/Forms/config", exc=ClientError)


@pytest.fixture
def unknown(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock Netgear LTE unknown error."""
    aioclient_mock.get(
        f"http://{HOST}/model.json",
        text="something went wrong",
        headers={"Content-Type": "application/javascript"},
    )


@pytest.fixture(name="connection")
def mock_connection(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock Netgear LTE connection."""
    aioclient_mock.get(
        f"http://{HOST}/model.json",
        text=load_fixture("netgear_lte/model.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.post(
        f"http://{HOST}/Forms/config",
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.post(
        f"http://{HOST}/Forms/smsSendMsg",
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create Netgear LTE entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN, data=CONF_DATA, unique_id="FFFFFFFFFFFFF", title="Netgear LM1200"
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    connection: None,
) -> None:
    """Set up the Netgear LTE integration in Home Assistant."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture(name="setup_cannot_connect")
async def setup_cannot_connect(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    cannot_connect: None,
) -> None:
    """Set up the Netgear LTE integration in Home Assistant."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
