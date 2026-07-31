"""Test the IntelliDwell Sprinkler Controller init module."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.intellidwell.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful setup and unload of a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry_unload",
    )
    entry.add_to_hass(hass)

    status_data = {
        "relay_states": [0] * 10,
        "timers": {},
        "queue": {},
    }

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value=status_data,
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            new_callable=AsyncMock,
            create=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
