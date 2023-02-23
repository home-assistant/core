"""Tests for the spc component."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyspcwebgw import SpcWebGateway

from homeassistant.components.spc import _async_update_callback
from homeassistant.components.spc.const import CONF_API_URL, CONF_WS_URL, DOMAIN
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from tests.common import MockConfigEntry

API_URL = "http://example.org"
WS_URL = "ws://example.org/ws/api"

CONF_DATA = {CONF_API_URL: API_URL, CONF_WS_URL: WS_URL}

CONF_CONFIG_FLOW = {CONF_API_URL: API_URL, CONF_WS_URL: WS_URL}

INVALID_CONFIG_ENTRY = MagicMock(data={CONF_API_URL: API_URL})


async def _create_mocked_spc(raise_exception=False):
    mocked_spc = AsyncMock()
    mocked_spc.get_state = AsyncMock()

    return mocked_spc


def _patch_config_flow_spc(mocked_spc):
    return patch(
        "homeassistant.components.spc.config_flow.SpcWebGateway",
        return_value=mocked_spc,
    )


async def setup_platform(hass, platform):
    """Set up the SPC platform and prerequisites."""
    hass.config.components.add(DOMAIN)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id=API_URL,
        entry_id="281c613684f295115f3948e7b9b1be94",
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = SpcWebGateway(
        loop=hass.loop,
        session=async_create_clientsession(hass),
        api_url=API_URL,
        ws_url=WS_URL,
        async_callback=lambda spc_object: _async_update_callback(hass, spc_object),
    )

    await hass.config_entries.async_forward_entry_setup(entry, platform)
    await hass.async_block_till_done()
    return entry
