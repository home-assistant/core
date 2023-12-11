"""Tests for the Arctic Spa integration."""

from unittest.mock import AsyncMock, MagicMock, Mock

from pyarcticspas import Spa

from homeassistant.components.arcticspa import CONF_API_KEY, Device
from homeassistant.components.arcticspa.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONF_API_KEY_VALUE = "mockapikey"


def _mock_device() -> Spa:
    spa = MagicMock(auto_spec=Spa, name="Mocked Arctic Spa Device")
    spa.async_status = AsyncMock()
    spa.status = Mock()
    spa.async_set_lights = AsyncMock()
    spa.set_lights = AsyncMock()
    return spa


async def initialize_config_entry_for_device(
    hass: HomeAssistant, dev: Device
) -> MockConfigEntry:
    """Create a mocked configuration entry for the given device."""

    config_entry = MockConfigEntry(
        title="Arctic Spa",
        domain=DOMAIN,
        unique_id=dev.id,
        data={CONF_API_KEY: CONF_API_KEY_VALUE},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
