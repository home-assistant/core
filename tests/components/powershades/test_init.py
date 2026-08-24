"""Tests for setting up and unloading the PowerShades integration."""

from unittest.mock import AsyncMock, patch

from pyowershades import PowerShadesConnection, PowerShadesTimeoutError

from homeassistant.components.powershades.const import DOMAIN
from homeassistant.components.powershades.coordinator import PowerShadesCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .conftest import TEST_IP, TEST_NAME, TEST_SERIAL

from tests.common import MockConfigEntry


async def test_setup_entry_success(hass: HomeAssistant, config_entry) -> None:
    """A working device sets up successfully with a coordinator and entities."""
    assert config_entry.state is ConfigEntryState.LOADED
    assert isinstance(config_entry.runtime_data, PowerShadesCoordinator)
    assert config_entry.runtime_data.data.position == 50

    assert len(hass.states.async_all("cover")) == 1


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """The entry retries setup if the device doesn't respond."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_IP, "serial": TEST_SERIAL, "name": TEST_NAME, "model": 1},
        unique_id=str(TEST_SERIAL),
    )
    entry.add_to_hass(hass)

    async def fake_request(op, payload=b"", timeout=None, retries=None):
        raise PowerShadesTimeoutError("no reply")

    with (
        patch.object(PowerShadesConnection, "async_connect", AsyncMock()),
        patch.object(
            PowerShadesConnection,
            "async_request",
            AsyncMock(side_effect=fake_request),
        ),
        patch.object(PowerShadesConnection, "close") as mock_close,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_close.assert_called_once()


async def test_unload_entry(hass: HomeAssistant, config_entry) -> None:
    """Unloading the entry unloads platforms and closes the connection."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    cover_states = hass.states.async_all("cover")
    assert len(cover_states) == 1
    assert cover_states[0].state == "unavailable"

    PowerShadesConnection.close.assert_called_once()
