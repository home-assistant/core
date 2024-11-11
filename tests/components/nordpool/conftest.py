"""Fixtures for the Nord Pool integration."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from unittest.mock import patch

from pynordpool import API, NordPoolClient
from pynordpool.const import Currency
from pynordpool.model import DeliveryPeriodData
import pytest

from homeassistant.components.nordpool.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.freeze_time("2024-11-05T18:00:00+00:00")
@pytest.fixture
async def load_int(
    hass: HomeAssistant, get_data: DeliveryPeriodData
) -> MockConfigEntry:
    """Set up the Nord Pool integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )

    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nordpool.coordinator.NordPoolClient.async_get_delivery_period",
            return_value=get_data,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="get_data")
async def get_data_from_library(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, load_data: str
) -> DeliveryPeriodData:
    """Retrieve data from Nord Pool library."""

    aioclient_mock.request(
        "get",
        API + "/DayAheadPrices",
        text=load_data,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )

    client = NordPoolClient(aioclient_mock.create_session(hass.loop))
    output = await client.async_get_delivery_period(
        datetime(2024, 11, 5, 13, tzinfo=dt_util.UTC), Currency.SEK, ["SE3", "SE4"]
    )
    await client._session.close()
    return output


@pytest.fixture(name="load_data", scope="package")
def load_data_from_fixture() -> str:
    """Load fixture with fixture data and return."""
    return load_fixture("delivery_period.json", DOMAIN)
