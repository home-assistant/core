"""Tests for the laundrify integration."""
import json
from unittest.mock import patch

from laundrify_aio import exceptions

from homeassistant.components.laundrify import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .const import VALID_ACCESS_TOKEN, VALID_ACCOUNT_ID

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


def _patch_laundrify_exchange_code():
    return patch(
        "laundrify_aio.LaundrifyAPI.exchange_auth_code",
        return_value=VALID_ACCESS_TOKEN,
    )


def _patch_laundrify_get_account_id():
    return patch(
        "laundrify_aio.LaundrifyAPI.get_account_id",
        return_value=VALID_ACCOUNT_ID,
    )


def _patch_laundrify_validate_token():
    return patch(
        "laundrify_aio.LaundrifyAPI.validate_token",
        return_value=True,
    )


def _patch_laundrify_get_machines():
    return patch(
        "laundrify_aio.LaundrifyAPI.get_machines",
        return_value=json.loads(load_fixture("laundrify/machines.json")),
    )


def create_entry(
    hass: HomeAssistant, access_token: str = VALID_ACCESS_TOKEN
) -> MockConfigEntry:
    """Create laundrify entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VALID_ACCOUNT_ID,
        data={CONF_ACCESS_TOKEN: access_token},
    )
    entry.add_to_hass(hass)
    return entry


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    access_token: str = VALID_ACCESS_TOKEN,
    error: bool = False,
) -> MockConfigEntry:
    """Set up the laundrify integration in Home Assistant."""
    entry = create_entry(hass, access_token=access_token)
    await mock_responses(hass, aioclient_mock, access_token=access_token, error=error)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def mock_responses(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    access_token: str = VALID_ACCESS_TOKEN,
    error: bool = False,
):
    """Mock responses from laundrify."""
    base_url = "https://test.laundrify.de/api"
    if error:
        aioclient_mock.get(
            f"{base_url}getInstant",
            exc=exceptions.ApiConnectionException,
        )
        return
    aioclient_mock.get(
        f"{base_url}/machines",
        text=load_fixture("laundrify/machines.json"),
    )
    if access_token == VALID_ACCESS_TOKEN:
        aioclient_mock.get(
            f"{base_url}/getCurrentValuesSummary",
            text=load_fixture("laundrify/machines.json"),
        )
    else:
        aioclient_mock.get(
            f"{base_url}/getCurrentValuesSummary",
            text=load_fixture("laundrify/machines.json"),
        )
