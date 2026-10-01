"""Tests for the Daikin Onecta sensor platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.daikin_onecta.const import DAIKIN_API_URL

from .conftest import FAKE_ACCESS_TOKEN, load_fixture_json


async def test_sensor_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up sensor entities from typed ONECTA data."""
    aioclient_mock.get(
        DAIKIN_API_URL + "/v1/gateway-devices",
        status=200,
        json=load_fixture_json("homehub"),
    )

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            new=AsyncMock(return_value=FAKE_ACCESS_TOKEN),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert entries
    assert any(entry.domain == SENSOR_DOMAIN for entry in entries)
