"""Test the epson init."""

from unittest.mock import patch

from homeassistant.components.epson.const import CONF_CONNECTION_TYPE, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test successful migration of entry data from version 1 to 1.2."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Epson",
        version=1,
        minor_version=1,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="1cb78c095906279574a0442a1f0003ef",
    )
    assert mock_entry.version == 1

    mock_entry.add_to_hass(hass)

    # Create entity entry to migrate to new unique ID
    with patch("homeassistant.components.epson.Projector.get_power"):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # Check that is now has connection_type
    assert mock_entry
    assert mock_entry.version == 1
    assert mock_entry.minor_version == 2
    assert mock_entry.data.get(CONF_CONNECTION_TYPE) == "http"
    assert mock_entry.data.get(CONF_HOST) == "1.1.1.1"
