"""Tests for the Modern Forms integration."""

from collections.abc import Callable
import json

from aiomodernforms.const import COMMAND_QUERY_STATIC_DATA

from homeassistant.components.modern_forms.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


async def modern_forms_call_mock(method, url, data):
    """Set up the basic returns based on info or status request."""
    if COMMAND_QUERY_STATIC_DATA in data:
        fixture = "modern_forms/device_info.json"
    else:
        fixture = "modern_forms/device_status.json"
    return AiohttpClientMockResponse(
        method=method, url=url, json=json.loads(load_fixture(fixture))
    )


async def modern_forms_no_light_call_mock(method, url, data):
    """Set up the basic returns based on info or status request."""
    if COMMAND_QUERY_STATIC_DATA in data:
        fixture = "modern_forms/device_info_no_light.json"
    else:
        fixture = "modern_forms/device_status_no_light.json"
    return AiohttpClientMockResponse(
        method=method, url=url, json=json.loads(load_fixture(fixture))
    )


async def modern_forms_timers_set_mock(method, url, data):
    """Set up the basic returns based on info or status request."""
    if COMMAND_QUERY_STATIC_DATA in data:
        fixture = "modern_forms/device_info.json"
    else:
        fixture = "modern_forms/device_status_timers_active.json"
    return AiohttpClientMockResponse(
        method=method, url=url, json=json.loads(load_fixture(fixture))
    )


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    rgbw: bool = False,
    skip_setup: bool = False,
    mock_type: Callable = modern_forms_call_mock,
) -> MockConfigEntry:
    """Set up the Modern Forms integration in Home Assistant."""

    aioclient_mock.post(
        "http://192.168.1.123:80/mf",
        side_effect=mock_type,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.123", CONF_MAC: "AA:BB:CC:DD:EE:FF"},
        unique_id="AA:BB:CC:DD:EE:FF",
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
