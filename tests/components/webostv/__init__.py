"""Tests for the LG webOS TV integration."""

from homeassistant.components.webostv.const import DOMAIN
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import CLIENT_KEY, FAKE_UUID, HOST, TV_NAME

from tests.common import MockConfigEntry


async def setup_webostv(
    hass: HomeAssistant, unique_id: str | None = FAKE_UUID
) -> MockConfigEntry:
    """Initialize webostv and media_player for tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_CLIENT_SECRET: CLIENT_KEY,
        },
        title=TV_NAME,
        unique_id=unique_id,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
