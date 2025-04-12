"""Generic tests for the Syncthru integration."""

from unittest.mock import AsyncMock

from homeassistant.components.syncthru import DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_v1_migration(
    hass: HomeAssistant,
    mock_syncthru: AsyncMock,
) -> None:
    """Test migration from v1 to v2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="C430W",
        data={CONF_URL: "http://192.168.1.2/"},
        minor_version=1,
    )
    await setup_integration(hass, entry)
    assert entry.minor_version == 2
    assert entry.unique_id == "08HRB8GJ3F019DD"
