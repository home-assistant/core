"""The tests for the Time & Date component."""

from homeassistant.components.time_date.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_remove_config_entry(hass: HomeAssistant) -> None:
    """Test setting up and removing a config entry."""
    # Setup the config entry

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={"display_options": ["time"]},
        options={"display_options": ["time"]},
        entry_id="123456abc",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the platform is setup correctly
    state = hass.states.get("sensor.time")
    assert state is not None

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state is removed, and does not reappear
    assert hass.states.get("sensor.time") is None
