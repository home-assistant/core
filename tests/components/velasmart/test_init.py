"""Tests for the VelaSmart integration."""

from unittest.mock import AsyncMock, patch

from velasmart import VelaSmartApiClient

from homeassistant.components.velasmart import async_setup_entry, async_unload_entry
from homeassistant.components.velasmart.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)

    with patch.object(
        VelaSmartApiClient, "get_devices", new_callable=AsyncMock, return_value=[]
    ):
        assert await async_setup_entry(hass, entry) is True
        await hass.async_block_till_done()

    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert "coordinator" in hass.data[DOMAIN][entry.entry_id]


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test@example.com", CONF_PASSWORD: "test"},
    )
    entry.add_to_hass(hass)

    with patch.object(
        VelaSmartApiClient, "get_devices", new_callable=AsyncMock, return_value=[]
    ):
        assert await async_setup_entry(hass, entry) is True
        await hass.async_block_till_done()

    assert await async_unload_entry(hass, entry) is True
    assert entry.entry_id not in hass.data[DOMAIN]
