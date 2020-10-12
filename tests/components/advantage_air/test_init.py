"""Test the Advantage Air Initialization."""

from advantage_air import ApiError

from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.components.advantage_air import (
    TEST_SYSTEM_DATA,
    TEST_SYSTEM_URL,
    add_mock_config,
)


async def test_async_setup_entry(hass, aioclient_mock):
    """Test a successful setup entry."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )

    entry = await add_mock_config(hass)

    assert isinstance(
        hass.data[DOMAIN][entry.entry_id]["coordinator"], DataUpdateCoordinator
    )
    assert callable(hass.data[DOMAIN][entry.entry_id]["async_change"])


async def test_async_setup_entry_failure(hass, aioclient_mock):
    """Test a unsuccessful setup entry."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        exc=ApiError("TestError"),
    )

    await add_mock_config(hass)
