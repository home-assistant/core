"""Test the sma init file."""

from collections.abc import AsyncGenerator

from homeassistant.components.sma.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant

from . import MOCK_DEVICE, MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_migrate_entry_minor_version_1_2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sma_client: AsyncGenerator,
) -> None:
    """Test migrating a 1.1 config entry to 1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE["name"],
        unique_id=MOCK_DEVICE["serial"],  # Not converted to str
        data=MOCK_USER_INPUT,
        source=SOURCE_IMPORT,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.unique_id == str(MOCK_DEVICE["serial"])
