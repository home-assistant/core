"""Tests for the BSBLan integration."""
import aiohttp

from homeassistant.components.bsblan.const import (
    CONF_DEVICE_IDENT,
    CONF_PASSKEY,
    DOMAIN,
)
from homeassistant.config_entries import ENTRY_STATE_SETUP_RETRY
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.bsblan import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_config_entry_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the BSBLan configuration entry not ready."""
    aioclient_mock.post(
        "http://example.local:80/1234/JQ?Parameter=6224,6225,6226",
        exc=aiohttp.ClientError,
    )

    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the BSBLan configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def test_config_entry_no_authentication(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the BSBLan configuration entry not ready."""
    aioclient_mock.post(
        "http://example.local:80/1234/JQ?Parameter=6224,6225,6226",
        exc=aiohttp.ClientError,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="RVS21.831F/127",
        data={
            CONF_HOST: "example.local",
            CONF_PASSKEY: "1234",
            CONF_PORT: 80,
            CONF_DEVICE_IDENT: "RVS21.831F/127",
        },
    )

    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ENTRY_STATE_SETUP_RETRY
