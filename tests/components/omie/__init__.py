"""Tests for the OMIE - Spain and Portugal electricity prices integration."""
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry


async def async_init_integration(
    hass: HomeAssistant, status=None
) -> MockConfigEntry:
    """Set up the OMIE integration for testing."""
    if status is None:
        status = MOCK_STATUS

    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="APCUPSd",
        data=CONF_DATA | {CONF_HOST: host},
        unique_id=status.get("SERIALNO", None),
        source=SOURCE_USER,
    )

    entry.add_to_hass(hass)

    with patch("aioapcaccess.request_status", return_value=status):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
