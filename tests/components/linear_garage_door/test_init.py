"""Test Linear Garage Door init."""

from unittest.mock import patch

from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test the unload entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-uuid",
        },
    )
    config_entry.add_to_hass(hass)

    with patch("linear_garage_door.Linear.login", return_value=True), patch(
        "linear_garage_door.Linear.get_devices",
        return_value=[
            {"id": "test", "name": "Test Garage", "subdevices": ["GDO", "Light"]}
        ],
    ), patch(
        "linear_garage_door.Linear.get_device_state",
        return_value={
            "GDO": {"Open_B": "true", "Open_P": "100"},
            "Light": {"On_B": "true", "On_P": "10"},
        },
    ), patch(
        "linear_garage_door.Linear.close",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state == ConfigEntryState.LOADED

    with patch("linear_garage_door.Linear.close", return_value=True):
        await hass.config_entries.async_unload(entries[0].entry_id)
        await hass.async_block_till_done()
    assert entries[0].state == ConfigEntryState.NOT_LOADED
