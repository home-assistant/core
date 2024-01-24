"""Tests for Efergy integration."""
from unittest.mock import AsyncMock, patch

from pyefergy import exceptions

from homeassistant.components.efergy import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TOKEN = "9p6QGJ7dpZfO3fqPTBk1fyEmjV1cGoLT"
MULTI_SENSOR_TOKEN = "9r6QGF7dpZfO3fqPTBl1fyRmjV1cGoLT"

CONF_DATA = {CONF_API_KEY: TOKEN}
HID = "12345678901234567890123456789012"

BASE_URL = "https://engage.efergy.com/mobile_proxy/"


def create_entry(hass: HomeAssistant, token: str = TOKEN) -> MockConfigEntry:
    """Create Efergy entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HID,
        data={CONF_API_KEY: token},
    )
    entry.add_to_hass(hass)
    return entry


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    token: str = TOKEN,
    error: bool = False,
) -> MockConfigEntry:
    """Set up the Efergy integration in Home Assistant."""
    entry = create_entry(hass, token=token)
    await mock_responses(hass, aioclient_mock, token=token, error=error)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


async def mock_responses(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    token: str = TOKEN,
    error: bool = False,
):
    """Mock responses from Efergy."""
    base_url = "https://engage.efergy.com/mobile_proxy/"
    if error:
        aioclient_mock.get(
            f"{base_url}getInstant?token={token}",
            exc=exceptions.ConnectError,
        )
        return
    aioclient_mock.get(
        f"{base_url}getStatus?token={token}",
        text=load_fixture("efergy/status.json"),
    )
    aioclient_mock.get(
        f"{base_url}getInstant?token={token}",
        text=load_fixture("efergy/instant.json"),
    )
    aioclient_mock.get(
        f"{base_url}getEnergy?period=day",
        text=load_fixture("efergy/daily_energy.json"),
    )
    aioclient_mock.get(
        f"{base_url}getEnergy?period=week",
        text=load_fixture("efergy/weekly_energy.json"),
    )
    aioclient_mock.get(
        f"{base_url}getEnergy?period=month",
        text=load_fixture("efergy/monthly_energy.json"),
    )
    aioclient_mock.get(
        f"{base_url}getEnergy?period=year",
        text=load_fixture("efergy/yearly_energy.json"),
    )
    aioclient_mock.get(
        f"{base_url}getBudget?token={token}",
        text=load_fixture("efergy/budget.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCost?period=day",
        text=load_fixture("efergy/daily_cost.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCost?period=week",
        text=load_fixture("efergy/weekly_cost.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCost?period=month",
        text=load_fixture("efergy/monthly_cost.json"),
    )
    aioclient_mock.get(
        f"{base_url}getCost?period=year",
        text=load_fixture("efergy/yearly_cost.json"),
    )
    if token == TOKEN:
        aioclient_mock.get(
            f"{base_url}getCurrentValuesSummary?token={token}",
            text=load_fixture("efergy/current_values_single.json"),
        )
    else:
        aioclient_mock.get(
            f"{base_url}getCurrentValuesSummary?token={token}",
            text=load_fixture("efergy/current_values_multi.json"),
        )


def _patch_efergy():
    mocked_efergy = AsyncMock()
    mocked_efergy.info = {}
    mocked_efergy.info["hid"] = HID
    mocked_efergy.info["mac"] = "AA:BB:CC:DD:EE:FF"
    mocked_efergy.info["status"] = "on"
    mocked_efergy.info["type"] = "EEEHub"
    mocked_efergy.info["version"] = "2.3.7"
    return patch(
        "homeassistant.components.efergy.config_flow.Efergy",
        return_value=mocked_efergy,
    )


def _patch_efergy_status():
    return patch("homeassistant.components.efergy.config_flow.Efergy.async_status")


async def setup_platform(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    platform: str,
    token: str = TOKEN,
    error: bool = False,
):
    """Set up the platform."""
    entry = await init_integration(hass, aioclient_mock, token=token, error=error)

    with patch("homeassistant.components.efergy.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})

    return entry
