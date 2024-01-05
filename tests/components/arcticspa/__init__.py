"""Tests for the Arctic Spa integration."""

from unittest.mock import AsyncMock, MagicMock, Mock

from pyarcticspas import Spa

from homeassistant.components.arcticspa import CONF_API_KEY
from homeassistant.components.arcticspa.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONF_API_KEY_VALUE = "mockapikey"
CONF_ID = "3b82ca882f2ebd283afc13c96209d6efc2e2b598ab6a9e02acb1090a55b7e643"  # id of "mockapikey"
CONF_NAME = "API-3b82ca88"


def _mock_spa() -> Spa:
    spa = MagicMock(auto_spec=Spa, name="Mocked Arctic Spa Device")
    spa.async_status = AsyncMock()
    spa.status = Mock()
    spa.async_set_lights = AsyncMock()
    spa.set_lights = AsyncMock()
    return spa


async def initialize_config_entry_for_device(
    hass: HomeAssistant, dev: Spa
) -> MockConfigEntry:
    """Create a mocked configuration entry for the given device."""

    config_entry = MockConfigEntry(
        title="Arctic Spa",
        domain=DOMAIN,
        data={CONF_API_KEY: CONF_API_KEY_VALUE},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
