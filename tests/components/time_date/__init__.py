"""Tests for the time_date component."""

from homeassistant.components.time_date.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DISPLAY_OPTIONS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def load_int(
    hass: HomeAssistant, display_option: str | None = None
) -> MockConfigEntry:
    """Set up the Time & Date integration in Home Assistant."""
    if display_option is None:
        display_option = "time"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={},
        options={CONF_DISPLAY_OPTIONS: display_option},
        entry_id=f"1234567890_{display_option}",
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
