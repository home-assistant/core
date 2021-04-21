"""Test the Advantage Air Initialization."""

from homeassistant.config_entries import EntryState

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
    assert entry.state is EntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is EntryState.NOT_LOADED


async def test_async_setup_entry_failure(hass, aioclient_mock):
    """Test a unsuccessful setup entry."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        exc=SyntaxError,
    )

    entry = await add_mock_config(hass)
    assert entry.state is EntryState.SETUP_RETRY
