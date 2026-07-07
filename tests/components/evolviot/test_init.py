"""Test the EvolvIOT integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.evolviot.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DATA_API,
    DATA_COORDINATOR,
    DATA_KNOWN_ENTITIES,
    DEFAULT_API_BASE_URL,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.evolviot.EvolvIOTDataUpdateCoordinator."
            "async_load_cache",
            new=AsyncMock(),
        ) as mock_load_cache,
        patch(
            "homeassistant.components.evolviot.EvolvIOTDataUpdateCoordinator."
            "async_config_entry_first_refresh",
            new=AsyncMock(),
        ) as mock_first_refresh,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as mock_forward_setups,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_load_cache.await_count == 1
    assert mock_first_refresh.await_count == 1
    mock_forward_setups.assert_awaited_once_with(entry, PLATFORMS)
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert DATA_API in hass.data[DOMAIN][entry.entry_id]
    assert DATA_COORDINATOR in hass.data[DOMAIN][entry.entry_id]
    assert hass.data[DOMAIN][entry.entry_id][DATA_KNOWN_ENTITIES] == {}


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
            CONF_ACCESS_TOKEN: "mock-access-token",
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.evolviot.EvolvIOTDataUpdateCoordinator."
            "async_load_cache",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.evolviot.EvolvIOTDataUpdateCoordinator."
            "async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ) as mock_unload_platforms,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)

    mock_unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.entry_id not in hass.data[DOMAIN]
