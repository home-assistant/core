"""Test the RainbowMiner integration setup."""

from homeassistant.components.rainbowminer.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import (
    TEST_BASE_URL,
    TEST_HOST,
    TEST_PORT,
    VALID_ACTIVE_MINERS,
    VALID_BALANCES,
    VALID_CURRENT_PROFIT,
    VALID_STATUS,
    VALID_UPTIME,
    VALID_VERSION,
    mock_rainbowminer_endpoints,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _create_entry() -> MockConfigEntry:
    """Return a mock RainbowMiner config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT},
    )


def _register_all(aioclient_mock: AiohttpClientMocker) -> None:
    """Register canned responses for all polled endpoints."""
    mock_rainbowminer_endpoints(
        aioclient_mock,
        status=VALID_STATUS,
        current_profit=VALID_CURRENT_PROFIT,
        uptime=VALID_UPTIME,
        active_miners=VALID_ACTIVE_MINERS,
        version=VALID_VERSION,
        balances=VALID_BALANCES,
    )


async def test_setup_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup and unload of the integration."""
    _register_all(aioclient_mock)
    entry = _create_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_with_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with username and password."""
    _register_all(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup retries when the version endpoint fails."""
    aioclient_mock.get(f"{TEST_BASE_URL}/version", exc=TimeoutError())
    mock_rainbowminer_endpoints(
        aioclient_mock,
        status=VALID_STATUS,
        current_profit=VALID_CURRENT_PROFIT,
        uptime=VALID_UPTIME,
        active_miners=VALID_ACTIVE_MINERS,
    )
    entry = _create_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
