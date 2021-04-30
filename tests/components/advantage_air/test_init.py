"""Test the Advantage Air Initialization."""

from homeassistant.config_entries import ConfigEntryState

from tests.components.advantage_air import (
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)


async def test_async_setup_entry(hass, aioclient_mock):
    """Test a successful setup entry and unload."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )

    entry = await add_mock_config(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_async_setup_entry_failure(hass, aioclient_mock):
    """Test a unsuccessful setup entry."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        exc=SyntaxError,
    )

    entry = await add_mock_config(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
