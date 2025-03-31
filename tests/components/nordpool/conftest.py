"""Fixtures for the Nord Pool integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json
from typing import Any

from pynordpool import API, NordPoolClient
import pytest

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
async def load_int(hass: HomeAssistant, get_client: NordPoolClient) -> MockConfigEntry:
    """Set up the Nord Pool integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="get_client")
async def get_data_from_library(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    load_json: list[dict[str, Any]],
) -> AsyncGenerator[NordPoolClient]:
    """Retrieve data from Nord Pool library."""
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-05",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=load_json[0],
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-05",
            "market": "DayAhead",
            "deliveryArea": "SE3",
            "currency": "EUR",
        },
        json=load_json[0],
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-04",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=load_json[1],
    )
    aioclient_mock.request(
        "GET",
        url=API + "/DayAheadPrices",
        params={
            "date": "2024-11-06",
            "market": "DayAhead",
            "deliveryArea": "SE3,SE4",
            "currency": "SEK",
        },
        json=load_json[2],
    )
    client = NordPoolClient(aioclient_mock.create_session(hass.loop))
    yield client
    await client._session.close()


@pytest.fixture(name="load_json")
def load_json_from_fixture(load_data: list[str, str, str]) -> list[dict[str, Any]]:
    """Load fixture with json data and return."""
    return [
        json.loads(load_data[0]),
        json.loads(load_data[1]),
        json.loads(load_data[2]),
    ]


@pytest.fixture(name="load_data", scope="package")
def load_data_from_fixture() -> list[str, str, str]:
    """Load fixture with fixture data and return."""
    return [
        load_fixture("delivery_period_today.json", DOMAIN),
        load_fixture("delivery_period_yesterday.json", DOMAIN),
        load_fixture("delivery_period_tomorrow.json", DOMAIN),
    ]
