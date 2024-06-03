"""Fixtures for the Sensibo integration."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from pysensibo import SensiboClient
from pysensibo.model import SensiboData
import pytest

from homeassistant.components.sensibo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
async def load_int(hass: HomeAssistant, get_data: SensiboData) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="username",
        version=2,
    )

    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices",
            return_value={"result": [{"id": "xyzxyz"}, {"id": "abcabc"}]},
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_me",
            return_value={"result": {"username": "username"}},
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="get_data")
async def get_data_from_library(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, load_json: dict[str, Any]
) -> SensiboData:
    """Retrieve data from upstream Sensibo library."""

    client = SensiboClient("123467890", aioclient_mock.create_session(hass.loop))
    with patch("pysensibo.SensiboClient.async_get_devices", return_value=load_json):
        output = await client.async_get_devices_data()
    await client._session.close()
    return output


@pytest.fixture(name="load_json")
def load_json_from_fixture(load_data: str) -> SensiboData:
    """Load fixture with json data and return."""
    json_data: dict[str, Any] = json.loads(load_data)
    return json_data


@pytest.fixture(name="load_data", scope="package")
def load_data_from_fixture() -> str:
    """Load fixture with fixture data and return."""
    return load_fixture("data.json", "sensibo")
